"""Treatment comparison for A/B, ad and pricing experiments."""

from collections import defaultdict
from itertools import pairwise
from typing import Any

from sqlalchemy.orm import Session

from simulacra.analysis import concept, stats
from simulacra.experiments.schemas import TOP_BOX
from simulacra.persistence.models import Trial

MIN_ARM_N = 10
ALPHA = 0.05
MONOTONE_TOLERANCE_P = 0.05


def _top(t: Trial) -> bool:
    return concept.parsed(t).get("purchase_intent") in TOP_BOX


def _appeal(t: Trial) -> float:
    return float(concept.parsed(t).get("appeal", 0))


def _pair_row(a: list[Trial], b: list[Trial]) -> dict[str, Any]:
    """Treatment (a) versus baseline (b) on independent groups."""
    ka, na, kb, nb = sum(map(_top, a)), len(a), sum(map(_top, b)), len(b)
    row: dict[str, Any] = {"n_treatment": na, "n_baseline": nb}
    if na == 0 or nb == 0:
        return row
    pa, pb = ka / na, kb / nb
    lo, hi = stats.newcombe_diff_ci(ka, na, kb, nb)
    row.update(
        {
            "top2_treatment": pa,
            "top2_baseline": pb,
            "diff": pa - pb,
            "diff_ci_low": lo,
            "diff_ci_high": hi,
            "p": stats.fisher_p(ka, na, kb, nb),
            "cohens_h": stats.cohens_h(pa, pb),
            "relative_lift": (pa - pb) / pb if pb > 0 else None,
            "appeal": stats.welch([_appeal(t) for t in a], [_appeal(t) for t in b]),
        }
    )
    return row


def _paired_row(a: list[Trial], b: list[Trial]) -> dict[str, Any]:
    """Within-subjects: each persona saw both treatments, so analyze matched pairs."""
    by_b = {t.persona_id: t for t in b}
    pairs = [(t, by_b[t.persona_id]) for t in a if t.persona_id in by_b]
    n = len(pairs)
    row: dict[str, Any] = {"n_treatment": n, "n_baseline": n, "paired": True}
    if n == 0:
        return row
    ka = sum(_top(x) for x, _ in pairs)
    kb = sum(_top(y) for _, y in pairs)
    only_a = sum(_top(x) and not _top(y) for x, y in pairs)
    only_b = sum(_top(y) and not _top(x) for x, y in pairs)
    pa, pb = ka / n, kb / n
    row.update(
        {
            "top2_treatment": pa,
            "top2_baseline": pb,
            "diff": pa - pb,
            "discordant": {"treatment_only": only_a, "baseline_only": only_b},
            "p": stats.mcnemar_exact_p(only_a, only_b),
            "cohens_h": stats.cohens_h(pa, pb),
            "relative_lift": (pa - pb) / pb if pb > 0 else None,
            "appeal": stats.paired_t(
                [_appeal(x) for x, _ in pairs], [_appeal(y) for _, y in pairs]
            ),
        }
    )
    return row


def compare(session: Session, run_id: int) -> dict[str, Any]:
    run, trials, personas, labels = concept.load(session, run_id)
    design = run.manifest_json.get("experiment", {}).get("config", {}).get("design", "between")
    # One observation per persona and treatment: repeats of the same persona are not independent,
    # so tests use the first repeat only. Extra repeats measure run-to-run variation instead.
    valid = [t for t in trials if t.status == "valid" and t.parsed_json and t.repeat_idx == 0]
    arms: dict[int, list[Trial]] = defaultdict(list)
    for t in valid:
        arms[t.treatment_idx].append(t)
    idxs = sorted(set(labels) | set(arms))
    out: dict[str, Any] = {
        "run_id": run_id,
        "design": design,
        "baseline_idx": 0,
        "pairs": [],
        "segments": [],
        "balance": None,
        "pricing": None,
        "notes": [],
    }
    if len(idxs) < 2:
        out["notes"].append("Only one treatment: nothing to compare.")
        return out

    base = arms.get(0, [])
    for idx in idxs[1:]:
        row = (
            _paired_row(arms.get(idx, []), base)
            if design == "within"
            else _pair_row(arms.get(idx, []), base)
        )
        row.update(
            {
                "treatment_idx": idx,
                "label": labels.get(idx, f"Treatment {idx}"),
                "vs": labels.get(0, "Treatment 0"),
            }
        )
        out["pairs"].append(row)
    ps = [r["p"] for r in out["pairs"] if r.get("p") is not None]
    adj = iter(stats.holm_adjust(ps))
    for r in out["pairs"]:
        if r.get("p") is not None:
            r["p_holm"] = next(adj)
            r["significant"] = r["p_holm"] < ALPHA

    # Exploratory heterogeneity: per segment, treatment versus baseline (independent designs).
    if design == "between":
        seg_rows: list[dict[str, Any]] = []
        for idx in idxs[1:]:
            for attribute in concept.SEGMENT_ATTRIBUTES:
                values = {
                    concept.segment_value(personas.get(t.persona_id, {}), attribute)
                    for t in arms.get(idx, [])
                }
                for value in sorted(v for v in values if v is not None):
                    a = [
                        t
                        for t in arms.get(idx, [])
                        if concept.segment_value(personas.get(t.persona_id, {}), attribute) == value
                    ]
                    b = [
                        t
                        for t in base
                        if concept.segment_value(personas.get(t.persona_id, {}), attribute) == value
                    ]
                    if len(a) < MIN_ARM_N or len(b) < MIN_ARM_N:
                        continue
                    r = _pair_row(a, b)
                    seg_rows.append(
                        {
                            "treatment_idx": idx,
                            "attribute": attribute,
                            "value": value,
                            **{
                                k: r[k]
                                for k in (
                                    "n_treatment",
                                    "n_baseline",
                                    "diff",
                                    "diff_ci_low",
                                    "diff_ci_high",
                                    "p",
                                )
                            },
                        }
                    )
        adj_seg = stats.holm_adjust([r["p"] for r in seg_rows])
        for r, p_adj in zip(seg_rows, adj_seg, strict=True):
            r["p_holm"], r["significant"] = p_adj, p_adj < ALPHA
        out["segments"] = seg_rows
        out["notes"].append(
            f"Segment comparisons are exploratory, require at least {MIN_ARM_N} valid responses in each arm, "
            f"and are Holm-adjusted across all {len(seg_rows)} tests."
        )
        out["balance"] = _balance(trials, personas)

    prices = {i: p for i in idxs if (p := _price(run.manifest_json, i)) is not None}
    if len(prices) == len(idxs):
        out["pricing"] = _pricing(idxs, prices, arms, labels)
    if any(t.repeat_idx > 0 for t in trials):
        out["notes"].append(
            "Tests use the first repeat of each persona so observations are independent."
        )
    out["notes"].append(
        "Differences are differences between simulated responses. A significant result means the model "
        "responded differently, not that real people would."
    )
    return out


def _price(manifest: dict[str, Any], idx: int) -> float | None:
    for t in manifest.get("experiment", {}).get("treatments", []):
        if t.get("idx") == idx:
            p = t.get("params", {}).get("price_usd")
            return float(p) if p is not None else None
    return None


def _pricing(
    idxs: list[int], prices: dict[int, float], arms: dict[int, list[Trial]], labels: dict[int, str]
) -> dict[str, Any]:
    ordered = sorted(idxs, key=lambda i: prices[i])
    rows: list[dict[str, Any]] = []
    for i in ordered:
        k, n = sum(map(_top, arms.get(i, []))), len(arms.get(i, []))
        lo, hi = concept.wilson(k, n)
        rows.append(
            {
                "treatment_idx": i,
                "label": labels.get(i, ""),
                "price_usd": prices[i],
                "n": n,
                "top2": k / n if n else None,
                "ci_low": lo,
                "ci_high": hi,
            }
        )
    violations = []
    for lo_row, hi_row in pairwise(rows):
        if not lo_row["n"] or not hi_row["n"]:
            continue
        k_lo, k_hi = round(lo_row["top2"] * lo_row["n"]), round(hi_row["top2"] * hi_row["n"])
        if hi_row["top2"] > lo_row["top2"]:
            p_greater = stats.fisher_p(k_hi, hi_row["n"], k_lo, lo_row["n"])
            if p_greater < MONOTONE_TOLERANCE_P:
                violations.append(
                    {
                        "lower_price": lo_row["price_usd"],
                        "higher_price": hi_row["price_usd"],
                        "p": p_greater,
                    }
                )
    return {
        "curve": rows,
        "monotone_violations": violations,
        "note": "Simulated purchase interest by price. This is not real demand and not a price elasticity.",
    }


def _balance(trials: list[Trial], personas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Did random assignment produce comparable groups? Chi-square per attribute, Holm adjusted."""
    assigned: dict[str, int] = {}
    for t in trials:
        assigned.setdefault(t.persona_id, t.treatment_idx)
    arms = sorted(set(assigned.values()))
    checks: list[dict[str, Any]] = []
    for attribute in concept.SEGMENT_ATTRIBUTES:
        vals = sorted(
            {
                v
                for pid in assigned
                if (v := concept.segment_value(personas.get(pid, {}), attribute)) is not None
            }
        )
        table = [
            [
                sum(
                    1
                    for pid, arm in assigned.items()
                    if arm == a and concept.segment_value(personas.get(pid, {}), attribute) == v
                )
                for v in vals
            ]
            for a in arms
        ]
        checks.append({"attribute": attribute, "p": stats.chi_square_p(table)})
    adj = stats.holm_adjust([c["p"] for c in checks])
    for c, p_adj in zip(checks, adj, strict=True):
        c["p_holm"] = p_adj
    return {
        "arm_sizes": {str(a): sum(1 for x in assigned.values() if x == a) for a in arms},
        "checks": checks,
        "min_p_holm": min(adj) if adj else None,
        "imbalanced": any(p < ALPHA for p in adj),
    }
