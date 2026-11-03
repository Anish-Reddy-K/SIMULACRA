"""Compare two runs of the same design (different model, prompt, or repeat of the same setup).

Trials are matched by (persona, treatment, repeat). Agreement is reported at the persona level,
so differences between models or prompts show up as measurable disagreement, not anecdotes.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra.analysis import concept, stats
from simulacra.experiments.schemas import TOP_BOX
from simulacra.persistence.models import Run, Trial


def cohens_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Chance-corrected agreement between two binary labelings of the same items."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def _model(run: Run) -> Any:
    return run.manifest_json.get("inference", {}).get("model")


def _top(t: Trial) -> bool:
    return concept.parsed(t).get("purchase_intent") in TOP_BOX


def compare_runs(session: Session, run_a: int, run_b: int) -> dict[str, Any]:
    ra, rb = session.get(Run, run_a), session.get(Run, run_b)
    if ra is None or rb is None:
        raise LookupError("no such run")

    def valid(rid: int) -> dict[tuple[str, int, int], Trial]:
        rows = session.scalars(select(Trial).where(Trial.run_id == rid, Trial.status == "valid"))
        return {(t.persona_id, t.treatment_idx, t.repeat_idx): t for t in rows if t.parsed_json}

    ta, tb = valid(run_a), valid(run_b)
    keys = sorted(set(ta) & set(tb))
    pairs = [(ta[k], tb[k]) for k in keys]
    n = len(pairs)
    out: dict[str, Any] = {
        "run_a": {
            "id": run_a,
            "model": _model(ra),
            "prompt": ra.manifest_json.get("prompt", {}).get("version"),
        },
        "run_b": {
            "id": run_b,
            "model": _model(rb),
            "prompt": rb.manifest_json.get("prompt", {}).get("version"),
        },
        "matched_trials": n,
        "only_in_a": len(set(ta) - set(tb)),
        "only_in_b": len(set(tb) - set(ta)),
        "notes": [
            "Only trials valid in both runs are compared.",
            "Disagreement between runs measures model or prompt sensitivity, not which one is right.",
        ],
    }
    if n == 0:
        return out
    top_a, top_b = [_top(x) for x, _ in pairs], [_top(y) for _, y in pairs]
    only_a = sum(x and not y for x, y in zip(top_a, top_b, strict=True))
    only_b = sum(y and not x for x, y in zip(top_a, top_b, strict=True))
    pa, pb = sum(top_a) / n, sum(top_b) / n
    appeals_a = [float(concept.parsed(x)["appeal"]) for x, _ in pairs]
    appeals_b = [float(concept.parsed(y)["appeal"]) for _, y in pairs]
    obj_same = sum(
        concept.parsed(x)["top_objection"] == concept.parsed(y)["top_objection"] for x, y in pairs
    )
    intent_same = sum(
        concept.parsed(x)["purchase_intent"] == concept.parsed(y)["purchase_intent"]
        for x, y in pairs
    )
    out.update(
        {
            "top2_a": pa,
            "top2_b": pb,
            "top2_diff": pa - pb,
            "top2_agreement": sum(x == y for x, y in zip(top_a, top_b, strict=True)) / n,
            "top2_kappa": cohens_kappa(top_a, top_b),
            "mcnemar_p": stats.mcnemar_exact_p(only_a, only_b),
            "discordant": {"a_only": only_a, "b_only": only_b},
            "intent_exact_agreement": intent_same / n,
            "objection_agreement": obj_same / n,
            "appeal": {
                "mean_a": sum(appeals_a) / n,
                "mean_b": sum(appeals_b) / n,
                **stats.paired_t(appeals_a, appeals_b),
            },
        }
    )
    return out
