"""Quality diagnostics for a generated population: fidelity to the spec, duplicates, diversity."""

import itertools
import random
from collections import Counter
from collections.abc import Iterable
from typing import Any

import numpy as np
from pydantic import BaseModel

from simulacra.populations.sampler import SampleResult
from simulacra.populations.spec import Categorical, Numeric, Ordinal, PopulationSpec

PAIR_SAMPLE = 200_000
DUPLICATE_JACCARD = 0.8


class MarginalCheck(BaseModel):
    attribute: str
    target: dict[str, float]
    realized: dict[str, float]
    max_abs_diff: float


class CorrelationCheck(BaseModel):
    a: str
    b: str
    target: float
    realized: float  # Spearman rank correlation of the realized values
    abs_diff: float


class Diagnostics(BaseModel):
    size: int
    marginals: list[MarginalCheck]
    max_marginal_diff: float
    correlations: list[CorrelationCheck]
    max_correlation_diff: float | None
    exact_duplicate_attribute_sets: int
    near_duplicate_bios: int | None  # None when bios were not compared
    bio_distinct_1: float | None
    bio_distinct_2: float | None
    unique_bios: int
    categorical_coverage: dict[str, float]  # share of spec categories that appear at least once
    rule_rejections: dict[str, int]
    unsatisfied_rules: int
    llm_fallbacks: int
    notes: list[str]


def _target_shares(spec: PopulationSpec, name: str) -> dict[str, float]:
    attr = spec.attributes[name]
    if isinstance(attr, Categorical):
        tot = sum(attr.weights.values())
        return {k: v / tot for k, v in attr.weights.items()}
    if isinstance(attr, Ordinal):
        tot = sum(attr.weights)
        return {lvl: w / tot for lvl, w in zip(attr.levels, attr.weights, strict=True)}
    assert isinstance(attr, Numeric)  # noqa: S101
    tot = sum(b.weight for b in attr.bins)
    return {f"{b.lo:g}-{b.hi:g}": b.weight / tot for b in attr.bins}


def _realized_shares(spec: PopulationSpec, name: str, values: list[Any]) -> dict[str, float]:
    attr = spec.attributes[name]
    n = len(values)
    if isinstance(attr, Numeric):
        out = {}
        for b in attr.bins:
            hi_incl = b is attr.bins[-1]
            cnt = sum(b.lo <= v < b.hi or (hi_incl and v == b.hi) for v in values)
            out[f"{b.lo:g}-{b.hi:g}"] = cnt / n
        return out
    counts = Counter(values)
    return {k: counts.get(k, 0) / n for k in _target_shares(spec, name)}


def _rank_values(spec: PopulationSpec, name: str, values: list[Any]) -> np.ndarray[Any, Any]:
    attr = spec.attributes[name]
    if isinstance(attr, Ordinal):
        order = {lvl: i for i, lvl in enumerate(attr.levels)}
        return np.array([order[v] for v in values], dtype=float)
    return np.array(values, dtype=float)


def _spearman(x: np.ndarray[Any, Any], y: np.ndarray[Any, Any]) -> float:
    def ranks(a: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        order = a.argsort(kind="stable")
        r = np.empty(len(a))
        sorted_a = a[order]
        i = 0
        while i < len(a):  # average ranks over ties
            j = i
            while j + 1 < len(a) and sorted_a[j + 1] == sorted_a[i]:
                j += 1
            r[order[i : j + 1]] = (i + j) / 2
            i = j + 1
        return r

    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def _shingles(text: str, k: int = 3) -> set[str]:
    words = text.lower().split()
    return {" ".join(words[i : i + k]) for i in range(max(1, len(words) - k + 1))}


def _near_duplicates(bios: list[str], seed: int) -> int:
    sets = [_shingles(b) for b in bios]
    n = len(sets)
    if n * (n - 1) // 2 <= PAIR_SAMPLE:
        pairs: Iterable[tuple[int, int]] = itertools.combinations(range(n), 2)
    else:
        rng = random.Random(seed)  # noqa: S311  (sampling pairs for a statistic, not security)
        pairs = ((rng.randrange(n), rng.randrange(n)) for _ in range(PAIR_SAMPLE))
    hits = 0
    for i, j in pairs:
        if i == j:
            continue
        inter = len(sets[i] & sets[j])
        union = len(sets[i] | sets[j])
        if union and inter / union >= DUPLICATE_JACCARD:
            hits += 1
    return hits


def compute(
    spec: PopulationSpec,
    sample: SampleResult,
    personas: list[dict[str, Any]],
) -> Diagnostics:
    """`personas` are the final persona dicts (attributes plus bio and meta)."""
    attrs = [p["attributes"] for p in personas]
    n = len(attrs)
    marginals = []
    for name in spec.attributes:
        target = _target_shares(spec, name)
        realized = _realized_shares(spec, name, [a[name] for a in attrs])
        diff = max(abs(target[k] - realized[k]) for k in target)
        marginals.append(
            MarginalCheck(attribute=name, target=target, realized=realized, max_abs_diff=diff)
        )

    corr = []
    for c in spec.correlations:
        x = _rank_values(spec, c.a, [a[c.a] for a in attrs])
        y = _rank_values(spec, c.b, [a[c.b] for a in attrs])
        got = _spearman(x, y)
        corr.append(
            CorrelationCheck(a=c.a, b=c.b, target=c.rho, realized=got, abs_diff=abs(got - c.rho))
        )

    keys = [tuple(sorted((k, str(v)) for k, v in a.items())) for a in attrs]
    exact_dups = n - len(set(keys))
    bios = [p.get("bio", "") for p in personas]
    have_bios = any(bios)
    tokens = [w for b in bios for w in b.lower().split()]
    bigrams = list(itertools.pairwise(tokens))
    coverage = {}
    for name, attr in spec.attributes.items():
        if isinstance(attr, Categorical | Ordinal):
            cats = set(attr.weights) if isinstance(attr, Categorical) else set(attr.levels)
            coverage[name] = len(cats & {a[name] for a in attrs}) / len(cats)
    notes = [
        "Realized-versus-target checks measure fidelity to the assumed spec, "
        "not to any real population.",
        "Spearman correlations are measured on rank-coded values; small samples are noisy.",
    ]
    if sample.rule_rejections:
        notes.append(
            "Hard rules are enforced by rejection sampling, which shifts the marginals of the "
            "attributes they involve (see the largest gaps above). Adjust the target weights if "
            "the realized shares matter."
        )
    if n * (n - 1) // 2 > PAIR_SAMPLE:
        notes.append(f"Near-duplicate bios were estimated from {PAIR_SAMPLE} random pairs.")
    return Diagnostics(
        size=n,
        marginals=marginals,
        max_marginal_diff=max((m.max_abs_diff for m in marginals), default=0.0),
        correlations=corr,
        max_correlation_diff=max((c.abs_diff for c in corr), default=None),
        exact_duplicate_attribute_sets=exact_dups,
        near_duplicate_bios=_near_duplicates(bios, spec.seed) if have_bios and n > 1 else None,
        bio_distinct_1=len(set(tokens)) / len(tokens) if tokens else None,
        bio_distinct_2=len(set(bigrams)) / len(bigrams) if bigrams else None,
        unique_bios=len(set(bios)),
        categorical_coverage=coverage,
        rule_rejections=sample.rule_rejections,
        unsatisfied_rules=sample.unsatisfied,
        llm_fallbacks=sum(
            1 for p in personas if p.get("meta", {}).get("enrichment") == "template_fallback"
        ),
        notes=notes,
    )
