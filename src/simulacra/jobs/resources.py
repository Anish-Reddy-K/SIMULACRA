"""Resource guard: watches disk and memory while a worker runs and pauses runs before the
machine is in trouble. Pausing is reversible; the run resumes from stored progress."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import psutil
from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra.jobs import queue
from simulacra.persistence.models import Run


@dataclass
class Thresholds:
    min_disk_mb: float = 1024.0  # pause when free disk on the data volume falls below this
    min_available_mb: float = 400.0  # pause when system-available memory stays below this
    low_memory_checks: int = 3  # consecutive checks, so a momentary dip does not pause a run
    check_every_s: float = 15.0
    report_every_s: float = 300.0  # a resource sample is recorded as a run event at this cadence


@dataclass
class Sample:
    disk_free_mb: float
    available_mb: float
    swap_used_mb: float


def sample(data_dir: Path) -> Sample:
    mem = psutil.virtual_memory()
    return Sample(
        disk_free_mb=shutil.disk_usage(data_dir).free / 2**20,
        available_mb=mem.available / 2**20,
        swap_used_mb=psutil.swap_memory().used / 2**20,
    )


class ResourceGuard:
    def __init__(self, data_dir: Path, thresholds: Thresholds | None = None) -> None:
        self.data_dir = data_dir
        self.t = thresholds or Thresholds()
        self._low_mem = 0
        self._last_check = 0.0
        self._last_report = 0.0

    def check(self, session: Session, now_s: float | None = None) -> list[str]:
        """Run at most once per interval. Returns the reasons runs were paused (if any)."""
        now_s = queue.now() if now_s is None else now_s
        if now_s - self._last_check < self.t.check_every_s:
            return []
        self._last_check = now_s
        s = sample(self.data_dir)
        running = list(session.scalars(select(Run).where(Run.state == "running")))
        if running and now_s - self._last_report >= self.t.report_every_s:
            self._last_report = now_s
            for run in running:
                queue.add_event(
                    session,
                    run.id,
                    "resource",
                    f"Resources: {s.available_mb:.0f} MB memory available, swap {s.swap_used_mb:.0f} MB, "
                    f"disk free {s.disk_free_mb / 1024:.1f} GB",
                )
        self._low_mem = self._low_mem + 1 if s.available_mb < self.t.min_available_mb else 0
        reasons: list[str] = []
        if s.disk_free_mb < self.t.min_disk_mb:
            reasons.append(
                f"free disk space is {s.disk_free_mb:.0f} MB (minimum {self.t.min_disk_mb:.0f} MB)"
            )
        if self._low_mem >= self.t.low_memory_checks:
            reasons.append(
                f"available memory stayed at {s.available_mb:.0f} MB (minimum {self.t.min_available_mb:.0f} MB)"
            )
        if reasons and running:
            for run in running:
                queue.control(session, run.id, "pause")
                queue.add_event(
                    session,
                    run.id,
                    "resource",
                    "Paused automatically: "
                    + "; ".join(reasons)
                    + ". Free up resources, then resume.",
                )
            session.commit()
            self._low_mem = 0
        return reasons
