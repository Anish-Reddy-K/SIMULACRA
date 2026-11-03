import asyncio
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from simulacra.benchmarks import workloads as wl
from simulacra.benchmarks.invariants import Diagnostic, consistency_score, score_consistency
from simulacra.benchmarks.memory import MemorySampler, pid_listening_on
from simulacra.benchmarks.metrics import Sample, WorkloadMetrics, aggregate
from simulacra.inference.base import InferenceBackend
from simulacra.inference.structured import generate_structured
from simulacra.inference.types import ModelInfo, RuntimeInfo

Stage = Literal["screen", "quick", "detailed", "soak"]
EvidenceQuality = Literal["screened", "quick", "detailed", "soak"]
STAGE_EVIDENCE: dict[Stage, EvidenceQuality] = {
    "screen": "screened",
    "quick": "quick",
    "detailed": "detailed",
    "soak": "soak",
}

# Concurrency sweep: keep doubling while throughput improves by at least this fraction.
SWEEP_LEVELS = (1, 2, 4, 8, 16)
SWEEP_MIN_GAIN = 0.10
SWEEP_MAX_FAILURE_RATE = 0.20

ProgressFn = Callable[[str, int, int], Awaitable[None]]


@dataclass
class Target:
    """One configuration under test: runtime + model (+ how structured output is requested)."""

    label: str
    backend: InferenceBackend
    model: str
    runtime: RuntimeInfo
    structured_mode: Literal["constrained", "prompted"] = "constrained"
    model_infos: list[ModelInfo] = field(default_factory=list)  # runtime's model list (digest etc.)
    pid: int | None = None  # server process for memory sampling; auto-detected from the port

    def resolved_pid(self) -> int | None:
        if self.pid is not None:
            return self.pid
        port = urlparse(self.runtime.base_url).port
        return pid_listening_on(port) if port else None


class CompatResult(BaseModel):
    ok: bool
    first_request_ms: float | None = None
    structured_valid_rate: float | None = None
    structured_json_schema_works: bool | None = None  # measured, never assumed
    error: str | None = None


class ResultRecord(BaseModel):
    """One persisted measurement: a workload run on one target at one concurrency."""

    model_config = {"arbitrary_types_allowed": True}

    workload: str
    stage: Stage
    evidence: EvidenceQuality
    concurrency: int
    workload_hash: str | None = None
    metrics: WorkloadMetrics | None = None
    diagnostics: list[Diagnostic] = []
    compat: CompatResult | None = None
    extras: dict[str, Any] = {}
    samples: list[Sample] = []


@dataclass
class TargetReport:
    target_label: str
    records: list[ResultRecord] = field(default_factory=list)
    skipped_reason: str | None = None


async def run_trials(
    target: Target,
    trials: list[wl.Trial],
    concurrency: int,
    on_progress: ProgressFn | None = None,
    op: str = "",
) -> tuple[list[Sample], float, MemorySampler]:
    """Execute trials with bounded concurrency; return samples in trial order, wall time, memory."""
    sem = asyncio.Semaphore(concurrency)
    samples: list[Sample | None] = [None] * len(trials)
    done = 0

    async def one(i: int, trial: wl.Trial) -> None:
        nonlocal done
        async with sem:
            outcome = await generate_structured(target.backend, trial.request, trial.schema)
        extra: dict[str, object] = dict(trial.meta)
        if outcome.parsed is not None:
            extra["parsed"] = outcome.parsed
        samples[i] = Sample(i, trial.group, outcome.status, outcome.generation, extra)
        done += 1
        if on_progress:
            await on_progress(op, done, len(trials))

    sampler = MemorySampler(target.resolved_pid())
    async with sampler:
        start = time.perf_counter()
        await asyncio.gather(*(one(i, t) for i, t in enumerate(trials)))
        wall = time.perf_counter() - start
    return [s for s in samples if s is not None], wall, sampler


async def _measure(
    target: Target,
    name: str,
    stage: Stage,
    trials: list[wl.Trial],
    concurrency: int,
    on_progress: ProgressFn | None,
) -> ResultRecord:
    samples, wall, sampler = await run_trials(
        target, trials, concurrency, on_progress, f"workload {name} (concurrency {concurrency})"
    )
    metrics = aggregate(samples, concurrency, wall)
    mem = sampler.stats()
    metrics.peak_rss_mb = mem.peak_rss_mb
    metrics.min_available_mb = mem.min_available_mb
    metrics.swap_growth_mb = mem.swap_growth_mb
    diagnostics = score_consistency(samples) if name == "F" else []
    return ResultRecord(
        workload=name,
        stage=stage,
        evidence=STAGE_EVIDENCE[stage],
        concurrency=concurrency,
        workload_hash=wl.workload_hash(trials),
        metrics=metrics,
        diagnostics=diagnostics,
        samples=samples,
    )


async def stage_compat(target: Target, on_progress: ProgressFn | None = None) -> ResultRecord:
    """Stage 1: can this configuration load, answer, and produce schema-valid output?"""
    probe = wl.workload_a(target.model, n=3)
    samples, _wall, _ = await run_trials(target, probe, 1, on_progress, "compatibility probe")
    first = samples[0].result if samples else None
    if first is None or not first.ok:
        err = first.error if first else "no response"
        compat = CompatResult(ok=False, error=err)
    else:
        valid = sum(s.status == "valid" for s in samples) / len(samples)
        compat = CompatResult(
            ok=True,
            first_request_ms=first.total_ms,
            structured_valid_rate=valid,
            structured_json_schema_works=valid == 1.0
            if target.structured_mode == "constrained"
            else None,
        )
    return ResultRecord(
        workload="compat",
        stage="screen",
        evidence="screened",
        concurrency=1,
        compat=compat,
        samples=samples,
    )


def _best_level(records: list[ResultRecord]) -> int:
    best = max(records, key=lambda r: r.metrics.valid_trials_per_min if r.metrics else 0.0)
    return best.concurrency


async def _sweep(
    target: Target, stage: Stage, on_progress: ProgressFn | None, per_level_min: int = 12
) -> list[ResultRecord]:
    """Workload B across rising concurrency until throughput plateaus or failures spike."""
    out: list[ResultRecord] = []
    for level in SWEEP_LEVELS:
        n = max(per_level_min, 4 * level)
        rec = await _measure(target, "B", stage, wl.workload_b(target.model, n), level, on_progress)
        out.append(rec)
        cur = rec.metrics
        if cur is None or cur.failure_rate > SWEEP_MAX_FAILURE_RATE:
            break
        prev = out[-2].metrics if len(out) >= 2 else None
        if prev is not None:
            gain = (cur.valid_trials_per_min - prev.valid_trials_per_min) / max(
                prev.valid_trials_per_min, 1e-9
            )
            if gain < SWEEP_MIN_GAIN:
                break
    return out


async def run_target(
    target: Target,
    stage: Stage,
    on_progress: ProgressFn | None = None,
    soak_seconds: float = 300.0,
    soak_concurrency: int = 2,
) -> TargetReport:
    report = TargetReport(target.label)
    compat = await stage_compat(target, on_progress)
    report.records.append(compat)
    if compat.compat is None or not compat.compat.ok:
        error = compat.compat.error if compat.compat else "no result"
        report.skipped_reason = f"compatibility check failed: {error}"
        return report
    if stage == "screen":
        return report

    m = target.model
    if stage == "quick":
        recs = [
            await _measure(target, "B", "quick", wl.workload_b(m, 16), 1, on_progress),
            await _measure(target, "B", "quick", wl.workload_b(m, 16), 4, on_progress),
            await _measure(target, "E", "quick", wl.workload_e(m, 8), 2, on_progress),
            await _measure(target, "F", "quick", wl.workload_f(m, reps=1), 2, on_progress),
        ]
        report.records += recs
        return report

    if stage == "detailed":
        sweep = await _sweep(target, "detailed", on_progress)
        report.records += sweep
        best = _best_level(sweep)
        # Repetitions at the best level give a measured dispersion of the headline metric.
        reps = [
            await _measure(
                target, "B", "detailed", wl.workload_b(m, max(24, 6 * best)), best, on_progress
            )
            for _ in range(3)
        ]
        rates = [r.metrics.valid_trials_per_min for r in reps if r.metrics]
        for r in reps:
            r.extras = {
                "repetition_rates": rates,
                "repetition_mean": statistics.fmean(rates),
                "repetition_cv": statistics.pstdev(rates) / statistics.fmean(rates)
                if statistics.fmean(rates)
                else None,
                "role": "repetition",
            }
        report.records += reps
        for name, fn, n, c in (
            ("A", wl.workload_a, 20, 1),
            ("C", wl.workload_c, 12, best),
            ("D", wl.workload_d, 120, best),
            ("E", wl.workload_e, 24, best),
        ):
            report.records.append(
                await _measure(target, name, "detailed", fn(m, n), c, on_progress)
            )
        report.records.append(
            await _measure(target, "F", "detailed", wl.workload_f(m, reps=4), 2, on_progress)
        )
        return report

    # soak: sustained workload G at a concurrency chosen by the caller via prior results (default 2)
    report.records.append(
        await _soak(target, soak_seconds, concurrency=soak_concurrency, on_progress=on_progress)
    )
    return report


async def _soak(
    target: Target,
    seconds: float,
    concurrency: int,
    on_progress: ProgressFn | None,
    window_s: float = 60.0,
) -> ResultRecord:
    """Workload G for a fixed duration; records per-window throughput to expose drift."""
    trials = wl.workload_g(target.model, n=100_000)
    sampler = MemorySampler(target.resolved_pid())
    samples: list[Sample] = []
    window_ends: list[float] = []
    nxt = 0
    start = time.perf_counter()
    stop_at = start + seconds
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal nxt
        while time.perf_counter() < stop_at:
            async with lock:
                i = nxt
                nxt += 1
            trial = trials[i]
            outcome = await generate_structured(target.backend, trial.request, trial.schema)
            samples.append(Sample(i, trial.group, outcome.status, outcome.generation))
            window_ends.append(time.perf_counter() - start)
            if on_progress:
                await on_progress(
                    f"soak (concurrency {concurrency})",
                    int(min(time.perf_counter() - start, seconds)),
                    int(seconds),
                )

    async with sampler:
        await asyncio.gather(*(worker() for _ in range(concurrency)))
    wall = time.perf_counter() - start
    metrics = aggregate(samples, concurrency, wall)
    mem = sampler.stats()
    metrics.peak_rss_mb, metrics.min_available_mb = mem.peak_rss_mb, mem.min_available_mb
    metrics.swap_growth_mb = mem.swap_growth_mb

    n_windows = max(1, int(wall // window_s))
    windows: list[dict[str, float | int | None]] = []
    for w in range(n_windows):
        lo, hi = w * window_s, (w + 1) * window_s
        in_w = [s for s, t in zip(samples, window_ends, strict=True) if lo <= t < hi]
        windows.append(
            {
                "window": w,
                "trials": len(in_w),
                "valid_per_min": sum(s.status == "valid" for s in in_w) / (window_s / 60),
                "failure_rate": (sum(s.status == "request_failed" for s in in_w) / len(in_w))
                if in_w
                else None,
            }
        )
    first = float(windows[0]["valid_per_min"] or 0.0)
    last = float(windows[-1]["valid_per_min"] or 0.0)
    return ResultRecord(
        workload="G",
        stage="soak",
        evidence="soak",
        concurrency=concurrency,
        workload_hash=wl.workload_hash(trials[: len(samples)]),
        metrics=metrics,
        extras={
            "duration_s": wall,
            "windows": windows,
            "throughput_drift": (last / first) if first else None,
            "note": "duration is what actually ran; an overnight soak is a separate, longer run",
        },
        samples=samples,
    )


def summarize_consistency(records: list[ResultRecord]) -> float | None:
    for r in reversed(records):
        if r.workload == "F" and r.diagnostics:
            return consistency_score(r.diagnostics)
    return None
