"""Seeded demographic sampling with a Gaussian copula for correlated attributes."""

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from simulacra.populations.rules import RULES
from simulacra.populations.spec import Categorical, Numeric, Ordinal, PopulationSpec

MAX_RULE_TRIES = 200

_erf = np.frompyfunc(math.erf, 1, 1)


def norm_cdf(z: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    return np.asarray(0.5 * (1.0 + _erf(z / math.sqrt(2.0))), dtype=float)


@dataclass
class SampleResult:
    personas: list[dict[str, Any]]
    rule_rejections: dict[str, int] = field(default_factory=dict)
    unsatisfied: int = 0  # personas that exhausted the retry budget (kept, flagged)


def correlation_matrix(spec: PopulationSpec) -> tuple[list[str], np.ndarray[Any, Any]]:
    names = sorted({n for c in spec.correlations for n in (c.a, c.b)})
    r = np.eye(len(names))
    for c in spec.correlations:
        i, j = names.index(c.a), names.index(c.b)
        r[i, j] = r[j, i] = c.rho
    if names and np.linalg.eigvalsh(r).min() < 1e-8:
        raise ValueError(
            "the correlations are not jointly achievable (matrix is not positive definite)"
        )
    return names, r


def _ordinal_value(attr: Ordinal, u: float) -> str:
    total = sum(attr.weights)
    acc = 0.0
    for level, w in zip(attr.levels, attr.weights, strict=True):
        acc += w / total
        if u <= acc:
            return level
    return attr.levels[-1]


def _numeric_value(attr: Numeric, u: float) -> int:
    total = sum(b.weight for b in attr.bins)
    acc = 0.0
    for b in attr.bins:
        share = b.weight / total
        if u <= acc + share or b is attr.bins[-1]:
            frac = min(1.0, max(0.0, (u - acc) / share))
            return min(int(b.hi) - 1, int(b.lo + frac * (b.hi - b.lo)))
        acc += share
    raise AssertionError("unreachable")


def _categorical(rng: np.random.Generator, attr: Categorical, count: int) -> list[str]:
    keys = list(attr.weights)
    p = np.array([attr.weights[k] for k in keys], dtype=float)
    return [keys[i] for i in rng.choice(len(keys), size=count, p=p / p.sum())]


def _strata_counts(attr: Categorical, size: int) -> list[tuple[str, int]]:
    """Largest-remainder allocation so realized shares match the spec as closely as possible."""
    total = sum(attr.weights.values())
    raw = {k: w / total * size for k, w in attr.weights.items()}
    counts = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[
        : size - sum(counts.values())
    ]:
        counts[k] += 1
    return list(counts.items())


def _draw_one(
    spec: PopulationSpec,
    rng: np.random.Generator,
    names: list[str],
    chol: np.ndarray[Any, Any] | None,
    fixed: dict[str, str],
) -> dict[str, Any]:
    u_corr: dict[str, float] = {}
    if chol is not None:
        z = chol @ rng.standard_normal(len(names))
        u_corr = dict(zip(names, norm_cdf(z).tolist(), strict=True))
    person: dict[str, Any] = {}
    for name, attr in spec.attributes.items():
        if name in fixed:
            person[name] = fixed[name]
        elif isinstance(attr, Categorical):
            person[name] = _categorical(rng, attr, 1)[0]
        else:
            u = u_corr.get(name, float(rng.random()))
            person[name] = (
                _ordinal_value(attr, u) if isinstance(attr, Ordinal) else _numeric_value(attr, u)
            )
    return person


def sample_population(spec: PopulationSpec) -> SampleResult:
    unknown = [r for r in spec.rules if r not in RULES]
    if unknown:
        raise ValueError(f"unknown rules: {unknown}")
    rng = np.random.default_rng(spec.seed)
    names, r = correlation_matrix(spec)
    chol = np.linalg.cholesky(r) if names else None

    slots: list[dict[str, str]]
    if spec.stratify_by:
        strat = spec.attributes[spec.stratify_by]
        assert isinstance(strat, Categorical)  # noqa: S101  (validated by the spec)
        slots = [
            {spec.stratify_by: k} for k, n in _strata_counts(strat, spec.size) for _ in range(n)
        ]
        order = rng.permutation(len(slots))  # interleave strata so index order carries no pattern
        slots = [slots[i] for i in order]
    else:
        slots = [{} for _ in range(spec.size)]

    result = SampleResult(personas=[])
    for fixed in slots:
        for _ in range(MAX_RULE_TRIES):
            person = _draw_one(spec, rng, names, chol, fixed)
            failed = [n for n in spec.rules if not RULES[n](person)]
            for n in failed:
                result.rule_rejections[n] = result.rule_rejections.get(n, 0) + 1
            if not failed:
                break
        else:
            result.unsatisfied += 1
        result.personas.append(person)
    return result
