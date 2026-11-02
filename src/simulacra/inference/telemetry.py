import statistics
from dataclasses import dataclass, field

from simulacra.inference.types import GenerationResult


@dataclass
class Telemetry:
    """Rolling in-memory aggregate of generation results (ETA, degradation detection)."""

    window: int = 500
    _results: list[GenerationResult] = field(default_factory=list)

    def record(self, result: GenerationResult) -> None:
        self._results.append(result)
        if len(self._results) > self.window:
            del self._results[0]

    @property
    def count(self) -> int:
        return len(self._results)

    @property
    def failure_rate(self) -> float | None:
        if not self._results:
            return None
        return sum(not r.ok for r in self._results) / len(self._results)

    def latency_ms(self, quantile: float) -> float | None:
        values = sorted(r.total_ms for r in self._results if r.ok)
        if not values:
            return None
        index = min(len(values) - 1, int(quantile * len(values)))
        return values[index]

    @property
    def median_decode_tokens_per_s(self) -> float | None:
        rates = [r.decode_tokens_per_s for r in self._results if r.decode_tokens_per_s]
        return statistics.median(rates) if rates else None
