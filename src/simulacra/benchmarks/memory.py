import asyncio
import contextlib
import subprocess
from dataclasses import dataclass

import psutil


def pid_listening_on(port: int) -> int | None:
    """PID of the local process listening on a TCP port (via lsof; no elevated rights)."""
    try:
        out = subprocess.run(  # noqa: S603
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return int(out[0]) if out else None


@dataclass
class MemoryStats:
    peak_rss_mb: float | None  # server process tree (includes children such as Ollama runners)
    min_available_mb: float  # whole system, lowest observed
    swap_growth_mb: float  # swap used at end minus at start
    samples: int


class MemorySampler:
    """Samples process-tree RSS and system memory while a workload runs.

    RSS under-reports GPU (Metal) allocations on Apple Silicon, so system-wide available
    memory and swap growth are recorded alongside it as the safety signals.
    """

    def __init__(self, pid: int | None, interval_s: float = 0.5) -> None:
        self.pid = pid
        self.interval_s = interval_s
        self._task: asyncio.Task[None] | None = None
        self._peak_rss = 0
        self._min_avail = psutil.virtual_memory().available
        self._swap_start = psutil.swap_memory().used
        self._swap_end = self._swap_start
        self._samples = 0

    def _sample(self) -> None:
        self._samples += 1
        self._min_avail = min(self._min_avail, psutil.virtual_memory().available)
        self._swap_end = psutil.swap_memory().used
        if self.pid is None:
            return
        try:
            proc = psutil.Process(self.pid)
            total = proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except psutil.Error:
                    continue
            self._peak_rss = max(self._peak_rss, total)
        except psutil.Error:
            return

    async def _loop(self) -> None:
        while True:
            self._sample()
            await asyncio.sleep(self.interval_s)

    async def __aenter__(self) -> "MemorySampler":
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._sample()

    def stats(self) -> MemoryStats:
        mb = 2**20
        return MemoryStats(
            peak_rss_mb=self._peak_rss / mb if self.pid is not None and self._peak_rss else None,
            min_available_mb=self._min_avail / mb,
            swap_growth_mb=max(0, self._swap_end - self._swap_start) / mb,
            samples=self._samples,
        )
