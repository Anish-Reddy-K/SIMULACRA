import statistics
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from simulacra.inference.structured import ValidationStatus
from simulacra.inference.types import GenerationResult

TokenRateMethod = Literal["runtime_reported", "client_derived", "unavailable"]


@dataclass
class Sample:
    """One measured trial. Kept so every aggregate can be audited."""

    index: int
    group: str
    status: ValidationStatus
    result: GenerationResult
    extra: dict[str, object] = field(default_factory=dict)


class WorkloadMetrics(BaseModel):
    n: int
    concurrency: int
    wall_s: float
    valid_rate: float
    invalid_json_rate: float
    schema_mismatch_rate: float
    failure_rate: float  # request failed (transport/runtime)
    timeout_rate: float
    valid_trials_per_min: float
    latency_ms_median: float | None
    latency_ms_p95: float | None
    ttft_ms_median: float | None
    decode_tokens_per_s_median: float | None
    decode_tps_method: TokenRateMethod
    prefill_tokens_per_s_median: float | None
    output_tokens_per_s_aggregate: float | None
    prompt_tokens_mean: float | None
    completion_tokens_mean: float | None
    first_request_ms: float | None
    peak_rss_mb: float | None = None
    min_available_mb: float | None = None
    swap_growth_mb: float | None = None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _is_timeout(r: GenerationResult) -> bool:
    return r.error is not None and "timeout" in r.error.lower()


def aggregate(samples: list[Sample], concurrency: int, wall_s: float) -> WorkloadMetrics:
    n = len(samples)
    if n == 0:
        raise ValueError("no samples to aggregate")
    results = [s.result for s in samples]
    ok = [r for r in results if r.ok]

    def count(status: str) -> int:
        return sum(s.status == status for s in samples)

    reported = [r.decode_tokens_per_s for r in ok if r.decode_tokens_per_s]
    derived = [
        r.completion_tokens / ((r.total_ms - r.ttft_ms) / 1000)
        for r in ok
        if r.completion_tokens and r.ttft_ms is not None and r.total_ms - r.ttft_ms > 1
    ]
    tps: float | None
    method: TokenRateMethod
    if reported:
        tps, method = _median(reported), "runtime_reported"
    elif derived:
        tps, method = _median(derived), "client_derived"
    else:
        tps, method = None, "unavailable"

    completion = [r.completion_tokens for r in ok if r.completion_tokens is not None]
    prompt = [r.prompt_tokens for r in ok if r.prompt_tokens is not None]
    return WorkloadMetrics(
        n=n,
        concurrency=concurrency,
        wall_s=wall_s,
        valid_rate=count("valid") / n,
        invalid_json_rate=count("invalid_json") / n,
        schema_mismatch_rate=count("schema_mismatch") / n,
        failure_rate=count("request_failed") / n,
        timeout_rate=sum(_is_timeout(r) for r in results) / n,
        valid_trials_per_min=count("valid") / (wall_s / 60) if wall_s > 0 else 0.0,
        latency_ms_median=_median([r.total_ms for r in ok]),
        latency_ms_p95=_quantile([r.total_ms for r in ok], 0.95),
        ttft_ms_median=_median([r.ttft_ms for r in ok if r.ttft_ms is not None]),
        decode_tokens_per_s_median=tps,
        decode_tps_method=method,
        prefill_tokens_per_s_median=_median(
            [r.prefill_tokens_per_s for r in ok if r.prefill_tokens_per_s]
        ),
        output_tokens_per_s_aggregate=sum(completion) / wall_s
        if completion and wall_s > 0
        else None,
        prompt_tokens_mean=statistics.fmean(prompt) if prompt else None,
        completion_tokens_mean=statistics.fmean(completion) if completion else None,
        first_request_ms=results[0].total_ms,
    )
