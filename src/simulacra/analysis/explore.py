"""Segment explorer and structured questions about a run.

Questions are structured (metric, grouping, filters), never free text fed to a model, so every
answer is computed from the stored trials and carries sample evidence.
"""

import statistics
from collections import defaultdict
from typing import Any, Literal

from sqlalchemy.orm import Session

from simulacra.analysis import concept
from simulacra.experiments.schemas import OBJECTIONS, PURCHASE_INTENTS, TOP_BOX
from simulacra.persistence.models import Trial

Metric = Literal["top2_share", "appeal_mean", "objection_share", "intent_share", "count"]
METRICS: tuple[str, ...] = ("top2_share", "appeal_mean", "objection_share", "intent_share", "count")
MAX_EVIDENCE = 3


class QueryError(ValueError):
    """The question is not valid (unknown attribute, metric, or value)."""


def _matches(t: Trial, attrs: dict[str, Any], filters: dict[str, str]) -> bool:
    return all(concept.segment_value(attrs, k) == v for k, v in filters.items())


def query(
    session: Session,
    run_id: int,
    metric: str,
    group_by: str | None = None,
    treatment: int | None = None,
    filters: dict[str, str] | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    if metric not in METRICS:
        raise QueryError(f"metric must be one of {METRICS}")
    for key in [*([group_by] if group_by else []), *(filters or {})]:
        if key not in concept.SEGMENT_ATTRIBUTES:
            raise QueryError(f"unknown attribute {key!r}; use one of {concept.SEGMENT_ATTRIBUTES}")
    if metric == "objection_share" and code not in OBJECTIONS:
        raise QueryError(f"objection_share needs code, one of {OBJECTIONS}")
    if metric == "intent_share" and code not in PURCHASE_INTENTS:
        raise QueryError(f"intent_share needs code, one of {PURCHASE_INTENTS}")
    _run, trials, personas, labels = concept.load(session, run_id)
    valid = [t for t in trials if t.status == "valid" and t.parsed_json and t.repeat_idx == 0]
    if treatment is not None:
        valid = [t for t in valid if t.treatment_idx == treatment]
    if filters:
        valid = [t for t in valid if _matches(t, personas.get(t.persona_id, {}), filters)]

    groups: dict[str, list[Trial]] = defaultdict(list)
    for t in valid:
        if not group_by:
            groups["all"].append(t)
        elif (value := concept.segment_value(personas.get(t.persona_id, {}), group_by)) is not None:
            groups[value].append(t)

    rows = []
    for key in sorted(groups):
        members = groups[key]
        n = len(members)
        row: dict[str, Any] = {
            "group": key,
            "n": n,
            "suppressed": n < concept.MIN_SEGMENT_N and bool(group_by),
            "evidence_trial_ids": [t.id for t in members[:MAX_EVIDENCE]],
        }
        if row["suppressed"]:
            rows.append(row)
            continue
        if metric == "count":
            row["value"] = n
        elif metric == "appeal_mean":
            row["value"] = statistics.fmean(float(concept.parsed(t)["appeal"]) for t in members)
        else:
            if metric == "top2_share":
                k = sum(concept.parsed(t)["purchase_intent"] in TOP_BOX for t in members)
            elif metric == "objection_share":
                k = sum(concept.parsed(t)["top_objection"] == code for t in members)
            else:
                k = sum(concept.parsed(t)["purchase_intent"] == code for t in members)
            lo, hi = concept.wilson(k, n)
            row.update({"value": k / n, "k": k, "ci_low": lo, "ci_high": hi})
        rows.append(row)
    return {
        "run_id": run_id,
        "metric": metric,
        "group_by": group_by,
        "treatment": treatment,
        "treatment_label": labels.get(treatment) if treatment is not None else None,
        "filters": filters or {},
        "code": code,
        "rows": rows,
        "notes": [
            "Computed from the first repeat of each persona's valid trials.",
            f"Groups with fewer than {concept.MIN_SEGMENT_N} valid responses are suppressed.",
            "Intervals describe sampling variation of this simulation only.",
        ],
    }
