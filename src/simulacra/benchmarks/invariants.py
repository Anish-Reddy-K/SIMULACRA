"""Behavioral-consistency scoring (workload F).

Deterministic invariants where one exists; plain stability numbers where a decision is
legitimately subjective. These are proxy checks of model behavior. They do not establish
that responses resemble real humans.
"""

from collections import Counter, defaultdict
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel

from simulacra.benchmarks.metrics import Sample
from simulacra.benchmarks.schemas import OwnershipCheck, PurchaseDecision

# Placeholder tolerances: documented, adjustable, to be revisited after Phase 4 baselines.
PRICE_MONOTONIC_TOLERANCE = 0.25
PARAPHRASE_MAX_SPREAD = 0.34


class Diagnostic(BaseModel):
    name: str
    kind: Literal["invariant", "stability"]
    value: float | None  # pass rate or agreement in [0, 1]; None when nothing was valid
    n_valid: int
    n_total: int
    threshold: float | None = None
    passed: bool | None = None
    detail: str = ""


def _decisions(samples: list[Sample], group: str) -> list[tuple[Sample, PurchaseDecision]]:
    out = []
    for s in samples:
        if s.group == group and s.status == "valid" and s.extra and "parsed" in s.extra:
            parsed = s.extra["parsed"]
            if isinstance(parsed, PurchaseDecision):
                out.append((s, parsed))
    return out


def _total(samples: list[Sample], group: str) -> int:
    return sum(s.group == group for s in samples)


def _buy_rate(items: list[tuple[Sample, PurchaseDecision]]) -> float | None:
    return sum(d.decision == "buy_now" for _, d in items) / len(items) if items else None


def _constraint(samples: list[Sample], group: str, name: str, detail: str) -> Diagnostic:
    items = _decisions(samples, group)
    value = sum(d.decision != "buy_now" for _, d in items) / len(items) if items else None
    return Diagnostic(
        name=name,
        kind="invariant",
        value=value,
        n_valid=len(items),
        n_total=_total(samples, group),
        threshold=1.0,
        passed=None if value is None else value >= 1.0,
        detail=detail,
    )


def _price_monotonic(samples: list[Sample]) -> Diagnostic:
    by_persona: dict[str, dict[int, list[tuple[Sample, PurchaseDecision]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for s, d in _decisions(samples, "price_sweep"):
        by_persona[str(s.extra["persona"])][int(str(s.extra["price"]))].append((s, d))
    checks, passes, notes = 0, 0, []
    for persona, prices in by_persona.items():
        rates = {p: _buy_rate(v) for p, v in sorted(prices.items()) if v}
        ordered = list(rates.items())
        for (p1, r1), (p2, r2) in pairwise(ordered):
            if r1 is None or r2 is None:
                continue
            checks += 1
            ok = r2 <= r1 + PRICE_MONOTONIC_TOLERANCE
            passes += ok
            if not ok:
                notes.append(
                    f"{persona}: buy rate rose from {r1:.2f} at ${p1} to {r2:.2f} at ${p2}"
                )
    value = passes / checks if checks else None
    return Diagnostic(
        name="price_monotonicity",
        kind="invariant",
        value=value,
        n_valid=checks,
        n_total=_total(samples, "price_sweep"),
        threshold=1.0,
        passed=None if value is None else value >= 1.0,
        detail="; ".join(notes) or "buy rate never rose materially with price",
    )


def _paraphrase(samples: list[Sample]) -> Diagnostic:
    by_persona: dict[str, dict[str, list[tuple[Sample, PurchaseDecision]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for s, d in _decisions(samples, "paraphrase"):
        by_persona[str(s.extra["persona"])][str(s.extra["style"])].append((s, d))
    spreads = []
    for styles in by_persona.values():
        rates = [r for v in styles.values() if (r := _buy_rate(v)) is not None]
        if len(rates) >= 2:
            spreads.append(max(rates) - min(rates))
    worst = max(spreads) if spreads else None
    return Diagnostic(
        name="paraphrase_invariance",
        kind="invariant",
        value=None if worst is None else 1.0 - worst,
        n_valid=len(spreads),
        n_total=_total(samples, "paraphrase"),
        threshold=1.0 - PARAPHRASE_MAX_SPREAD,
        passed=None if worst is None else worst <= PARAPHRASE_MAX_SPREAD,
        detail="1 minus the largest buy-rate spread across equivalent wordings",
    )


def _stability(samples: list[Sample]) -> Diagnostic:
    by_persona: dict[str, list[str]] = defaultdict(list)
    for s, d in _decisions(samples, "stability"):
        by_persona[str(s.extra["persona"])].append(d.decision)
    shares = [Counter(v).most_common(1)[0][1] / len(v) for v in by_persona.values() if v]
    value = sum(shares) / len(shares) if shares else None
    return Diagnostic(
        name="repeated_trial_agreement",
        kind="stability",
        value=value,
        n_valid=sum(len(v) for v in by_persona.values()),
        n_total=_total(samples, "stability"),
        detail="mean share of the modal decision across identical prompts "
        "(subjective: variation is legitimate, reported as stability only)",
    )


def _memory(samples: list[Sample]) -> Diagnostic:
    hits, n = 0, 0
    for s in samples:
        if s.group == "memory" and s.status == "valid" and s.extra and "parsed" in s.extra:
            parsed = s.extra["parsed"]
            if isinstance(parsed, OwnershipCheck):
                n += 1
                hits += parsed.owns_similar_product == s.extra["expected"]
    return Diagnostic(
        name="memory_fact_recall",
        kind="invariant",
        value=hits / n if n else None,
        n_valid=n,
        n_total=_total(samples, "memory"),
        threshold=1.0,
        passed=None if not n else hits == n,
        detail="persona-card fact recalled correctly",
    )


def score_consistency(samples: list[Sample]) -> list[Diagnostic]:
    return [
        _constraint(
            samples,
            "constraint",
            "budget_constraint",
            "constrained persona (low budget, no credit) must not choose buy_now at $600",
        ),
        _price_monotonic(samples),
        _paraphrase(samples),
        _constraint(
            samples,
            "instruction_conflict",
            "persona_over_injected_instruction",
            "persona finances must win over an instruction embedded in the offer text",
        ),
        _memory(samples),
        _stability(samples),
    ]


def consistency_score(diagnostics: list[Diagnostic]) -> float | None:
    """Mean of invariant values only (stability is reported, not scored). None if no data."""
    values = [d.value for d in diagnostics if d.kind == "invariant" and d.value is not None]
    return sum(values) / len(values) if values else None
