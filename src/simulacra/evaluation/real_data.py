"""Evaluate simulated results against real human observations.

Input is a CSV of real respondents: one row per person, a binary or ordinal outcome column, and
segment attribute columns that use the same names and values as the simulation's personas. The
simulation is a *prediction* of the real outcome per segment; this module measures how good that
prediction is, including the failure modes documented for synthetic respondents (compressed
variation, over-agreement, miscalibration). Nothing here is evidence unless real data is supplied.
"""

import csv
import io
import math
import statistics
from dataclasses import dataclass
from typing import Any

MAX_ROWS = 200_000
MIN_SEGMENT_N = 15


class EvaluationError(ValueError):
    pass


@dataclass
class Observation:
    segment: str  # "attribute=value"
    n_real: int
    real: float  # share of real respondents with the positive outcome
    n_sim: int
    sim: float


def parse_real_csv(
    raw: bytes, outcome_column: str, positive_values: set[str]
) -> list[dict[str, str]]:
    """Validate and parse a real-respondent CSV. Strict: unknown shapes are rejected, not guessed."""
    if len(raw) > 50 * 2**20:
        raise EvaluationError("file is larger than 50 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EvaluationError("file is not valid UTF-8 text") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or outcome_column not in reader.fieldnames:
        raise EvaluationError(f"the CSV needs an {outcome_column!r} column")
    rows = []
    for i, row in enumerate(reader, start=2):
        if i > MAX_ROWS:
            raise EvaluationError(f"more than {MAX_ROWS} rows")
        value = (row.get(outcome_column) or "").strip()
        if value == "":
            continue  # missing outcome: excluded, and counted by the caller
        row[outcome_column] = "1" if value.lower() in positive_values else "0"
        rows.append(row)
    if not rows:
        raise EvaluationError("no usable rows (every outcome was missing)")
    return rows


def segment_observations(
    real_rows: list[dict[str, str]],
    outcome_column: str,
    sim_segments: list[dict[str, Any]],
    attributes: list[str],
) -> list[Observation]:
    """Join real shares to simulated shares per segment value. `sim_segments` rows come from
    `explore.query(..., "top2_share", group_by=attribute)`: {attribute, group, n, value}."""
    out: list[Observation] = []
    sim_lookup = {
        (s["attribute"], s["group"]): s for s in sim_segments if s.get("value") is not None
    }
    for attribute in attributes:
        values = {r.get(attribute, "") for r in real_rows} - {""}
        for value in sorted(values):
            members = [r for r in real_rows if r.get(attribute) == value]
            sim = sim_lookup.get((attribute, value))
            if len(members) < MIN_SEGMENT_N or sim is None:
                continue
            out.append(
                Observation(
                    f"{attribute}={value}",
                    len(members),
                    sum(int(r[outcome_column]) for r in members) / len(members),
                    int(sim["n"]),
                    float(sim["value"]),
                )
            )
    return out


def _ols(x: list[float], y: list[float]) -> tuple[float, float] | None:
    """Slope and intercept of y on x. A calibrated simulation has slope 1 and intercept 0."""
    if len(x) < 3 or statistics.pvariance(x) == 0:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sum(
        (a - mx) ** 2 for a in x
    )
    return slope, my - slope * mx


def evaluate(obs: list[Observation], overall_real: float, overall_sim: float) -> dict[str, Any]:
    """Agreement, calibration and failure-mode diagnostics between simulation and reality."""
    if len(obs) < 3:
        raise EvaluationError("need at least 3 comparable segments to evaluate")
    sim, real = [o.sim for o in obs], [o.real for o in obs]
    errors = [s - r for s, r in zip(sim, real, strict=True)]
    ols = _ols(sim, real)
    spearman = stats_spearman(sim, real)
    sd_sim, sd_real = statistics.pstdev(sim), statistics.pstdev(real)
    worst = sorted(obs, key=lambda o: -abs(o.sim - o.real))[:5]
    return {
        "n_segments": len(obs),
        "overall": {
            "real": overall_real,
            "simulated": overall_sim,
            "error": overall_sim - overall_real,
        },
        "mae": statistics.fmean(abs(e) for e in errors),
        "rmse": math.sqrt(statistics.fmean(e * e for e in errors)),
        "bias": statistics.fmean(errors),
        "pearson": _pearson(sim, real),
        "spearman": spearman,
        "calibration": None if ols is None else {"slope": ols[0], "intercept": ols[1]},
        "variation_ratio": sd_sim / sd_real if sd_real > 0 else None,
        "worst_segments": [
            {
                "segment": o.segment,
                "real": o.real,
                "simulated": o.sim,
                "error": o.sim - o.real,
                "n_real": o.n_real,
            }
            for o in worst
        ],
        "interpretation": [
            "Bias above zero means the simulation over-predicts positive outcomes (over-agreement).",
            "A variation ratio below 1 means simulated segments differ less than real ones (compressed variation).",
            "A calibration slope below 1 means simulated differences between segments are exaggerated relative to reality; above 1, understated.",
            "Segment-level agreement says nothing about individual-level accuracy.",
        ],
    }


def _pearson(a: list[float], b: list[float]) -> float | None:
    if statistics.pstdev(a) == 0 or statistics.pstdev(b) == 0:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def stats_spearman(a: list[float], b: list[float]) -> float | None:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out

    return _pearson(ranks(a), ranks(b))


def compare_distributions(sim: list[float], real: list[float]) -> dict[str, float]:
    """Total variation distance and Jensen-Shannon divergence between two categorical shares."""
    if len(sim) != len(real) or not sim:
        raise EvaluationError("distributions need the same categories")
    tv = 0.5 * sum(abs(a - b) for a, b in zip(sim, real, strict=True))
    m = [(a + b) / 2 for a, b in zip(sim, real, strict=True)]

    def kl(p: list[float], q: list[float]) -> float:
        return sum(a * math.log2(a / b) for a, b in zip(p, q, strict=True) if a > 0)

    return {"total_variation": tv, "jensen_shannon": 0.5 * kl(sim, m) + 0.5 * kl(real, m)}
