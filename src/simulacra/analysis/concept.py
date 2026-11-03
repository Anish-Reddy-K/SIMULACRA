"""Deterministic analysis of experiment trials. No LLM is involved in any number here.

Intervals are Wilson intervals describing sampling variation of THIS simulation's responses.
They are not uncertainty about real human behavior.
"""

import math
import statistics
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra.experiments.schemas import OBJECTIONS, PURCHASE_INTENTS, TOP_BOX
from simulacra.persistence.models import PersonaRow, Run, Treatment, Trial

MIN_SEGMENT_N = 10
SEGMENT_ATTRIBUTES = (
    "age_band",
    "income_band",
    "region",
    "gender",
    "education",
    "employment",
    "household",
    "tech_adoption",
    "price_sensitivity",
)
DIVERGENCE_POINTS = 0.20
QUOTES_PER_CODE = 2
BOTTOM_BOX = ("probably_not", "definitely_not")


def parsed(t: Trial) -> dict[str, Any]:
    return t.parsed_json or {}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def age_band(age: int) -> str:
    if age < 30:
        return "18-29"
    if age < 45:
        return "30-44"
    if age < 60:
        return "45-59"
    return "60+"


def segment_value(attrs: dict[str, Any], attribute: str) -> str | None:
    if attribute == "age_band":
        return age_band(int(attrs["age"])) if "age" in attrs else None
    value = attrs.get(attribute)
    return None if value is None else str(value)


def _share(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"n": k, "of": n, "share": k / n if n else None, "ci_low": lo, "ci_high": hi}


def _dist(counter: Counter[str], keys: tuple[str, ...], total: int) -> list[dict[str, Any]]:
    return [
        {"code": k, "n": counter.get(k, 0), "share": counter.get(k, 0) / total if total else None}
        for k in keys
    ]


def load(
    session: Session, run_id: int
) -> tuple[Run, list[Trial], dict[str, dict[str, Any]], dict[int, str]]:
    run = session.get(Run, run_id)
    if run is None:
        raise LookupError("no such run")
    trials = list(session.scalars(select(Trial).where(Trial.run_id == run_id).order_by(Trial.id)))
    version_id = int(run.config_json.get("population_version_id", 0))
    personas = {
        r.synthetic_id: dict(r.attributes_json)
        for r in session.scalars(select(PersonaRow).where(PersonaRow.version_id == version_id))
    }
    exp_id = run.config_json.get("experiment_id")
    labels = {
        t.idx: t.label
        for t in session.scalars(select(Treatment).where(Treatment.experiment_id == exp_id))
    }
    return run, trials, personas, labels


def analyze(session: Session, run_id: int) -> dict[str, Any]:
    run, trials, personas, labels = load(session, run_id)
    by_status = Counter(t.status for t in trials)
    valid = [t for t in trials if t.status == "valid" and t.parsed_json]
    total = len(trials)

    treatments_out = []
    for idx in sorted({t.treatment_idx for t in trials} | set(labels)):
        rows = [t for t in valid if t.treatment_idx == idx]
        n = len(rows)
        intents = Counter(parsed(t)["purchase_intent"] for t in rows)
        appeals = [int(parsed(t)["appeal"]) for t in rows]
        benefits = Counter(parsed(t)["top_benefit"] for t in rows)
        objections = Counter(parsed(t)["top_objection"] for t in rows)
        top = sum(intents[k] for k in TOP_BOX)
        bottom = sum(intents[k] for k in BOTTOM_BOX)
        treatments_out.append(
            {
                "idx": idx,
                "label": labels.get(idx, f"Treatment {idx}"),
                "n_trials": sum(1 for t in trials if t.treatment_idx == idx),
                "n_valid": n,
                "intent": _dist(intents, PURCHASE_INTENTS, n),
                "top2box": _share(top, n),
                "bottom2box": _share(bottom, n),
                "appeal": {
                    "mean": statistics.fmean(appeals) if appeals else None,
                    "sd": statistics.pstdev(appeals) if len(appeals) > 1 else None,
                    "n": n,
                },
                "benefits": _dist(benefits, tuple(sorted(benefits)), n),
                "objections": _dist(objections, OBJECTIONS, n),
            }
        )

    segments = _segments(valid, personas)
    contradictions = _contradictions(valid, treatments_out, segments)
    return {
        "run_id": run_id,
        "totals": {
            "trials": total,
            "valid": len(valid),
            "by_status": dict(by_status),
            "invalid_rate": (total - len(valid)) / total if total else None,
            "planned": run.total_units,
        },
        "treatments": treatments_out,
        "segments": segments,
        "objections": _ranked(valid, "top_objection", exclude=("none",)),
        "benefits": _ranked(valid, "top_benefit", exclude=("none",)),
        "quotes": _quotes(valid),
        "contradictions": contradictions,
        "repeat_stability": _repeat_stability(valid),
        "notes": [
            "Intervals describe sampling variation of this simulation, not uncertainty about real people.",
            f"Segments with fewer than {MIN_SEGMENT_N} valid responses are suppressed.",
        ],
    }


def _segments(valid: list[Trial], personas: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[Trial]] = defaultdict(list)
    for t in valid:
        attrs = personas.get(t.persona_id)
        if attrs is None:
            continue
        for attribute in SEGMENT_ATTRIBUTES:
            value = segment_value(attrs, attribute)
            if value is not None:
                groups[(attribute, value, t.treatment_idx)].append(t)
    out = []
    for (attribute, value, tidx), rows in sorted(groups.items()):
        n = len(rows)
        row: dict[str, Any] = {
            "attribute": attribute,
            "value": value,
            "treatment_idx": tidx,
            "n": n,
            "suppressed": n < MIN_SEGMENT_N,
        }
        if n >= MIN_SEGMENT_N:
            top = sum(parsed(t)["purchase_intent"] in TOP_BOX for t in rows)
            row["top2box"] = _share(top, n)
            row["appeal_mean"] = statistics.fmean(int(parsed(t)["appeal"]) for t in rows)
        out.append(row)
    return out


def _ranked(valid: list[Trial], field: str, exclude: tuple[str, ...]) -> list[dict[str, Any]]:
    counts = Counter(parsed(t)[field] for t in valid if t.parsed_json)
    n = len(valid)
    return [
        {"code": c, "n": k, "share": k / n if n else None}
        for c, k in counts.most_common()
        if c not in exclude
    ]


def _quotes(valid: list[Trial]) -> list[dict[str, Any]]:
    """Deterministic choice: earliest trials per reason code. Each links to its source trial."""
    out: list[dict[str, Any]] = []
    for field, ranking in (
        ("top_objection", _ranked(valid, "top_objection", ("none",))),
        ("top_benefit", _ranked(valid, "top_benefit", ("none",))),
    ):
        for item in ranking[:3]:
            picked = [t for t in valid if t.parsed_json and parsed(t)[field] == item["code"]]
            for t in picked[:QUOTES_PER_CODE]:
                out.append(
                    {
                        "kind": field,
                        "code": item["code"],
                        "trial_id": t.id,
                        "persona_id": t.persona_id,
                        "treatment_idx": t.treatment_idx,
                        "text": parsed(t)["reason"],
                    }
                )
    return out


def _contradictions(
    valid: list[Trial], treatments: list[dict[str, Any]], segments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    odd = [
        t
        for t in valid
        if t.parsed_json
        and int(parsed(t)["appeal"]) >= 4
        and parsed(t)["purchase_intent"] in BOTTOM_BOX
    ]
    if odd:
        found.append(
            {
                "kind": "high_appeal_low_intent",
                "n": len(odd),
                "of": len(valid),
                "description": "Responses with appeal 4-5 but intent probably_not or definitely_not",
                "example_trial_ids": [t.id for t in odd[:5]],
            }
        )
    for tr in treatments:
        overall = tr["top2box"]["share"]
        if overall is None:
            continue
        for seg in segments:
            if seg["treatment_idx"] != tr["idx"] or seg["suppressed"]:
                continue
            gap = seg["top2box"]["share"] - overall
            if abs(gap) >= DIVERGENCE_POINTS:
                found.append(
                    {
                        "kind": "diverging_segment",
                        "treatment_idx": tr["idx"],
                        "attribute": seg["attribute"],
                        "value": seg["value"],
                        "n": seg["n"],
                        "gap_points": gap * 100,
                        "description": f"{seg['attribute']}={seg['value']} differs from the overall "
                        f"top-2-box share by {gap * 100:+.0f} points",
                    }
                )
    return found


def _repeat_stability(valid: list[Trial]) -> dict[str, Any] | None:
    """Run-to-run variation: how consistent is the same persona across repeated trials?"""
    groups: dict[tuple[str, int], list[Trial]] = defaultdict(list)
    for t in valid:
        groups[(t.persona_id, t.treatment_idx)].append(t)
    multi = [g for g in groups.values() if len(g) > 1]
    if not multi:
        return None
    same_top = sum(len({parsed(t)["purchase_intent"] in TOP_BOX for t in g}) == 1 for g in multi)
    same_intent = sum(len({parsed(t)["purchase_intent"] for t in g}) == 1 for g in multi)
    return {
        "personas_with_repeats": len(multi),
        "top2_agreement": same_top / len(multi),
        "intent_exact_agreement": same_intent / len(multi),
        "note": "Share of persona-treatment cells whose repeated trials gave the same answer.",
    }
