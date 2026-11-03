"""Assemble and render reports. Every sentence about numbers is generated from computed data."""

import html
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from simulacra.analysis import compare as compare_mod
from simulacra.analysis import concept
from simulacra.persistence.models import PopulationVersion, Run

LIMITATIONS = [
    "These are simulated opinions from model-generated personas. They are not observed human "
    "behavior and not validated predictions.",
    "Personas follow an assumed distribution, not a representative sample of any real population.",
    "Small local language models tend to agree with offers, give generic reasons and under-represent "
    "real variation in opinion; results can depend strongly on prompt wording and on the model.",
    "Intervals describe sampling variation of this simulation only. They are not confidence in "
    "real-world behavior.",
    "Stated purchase intent is not purchase behavior, even among real people.",
]

FOLLOW_UP = [
    "Treat the objections and segment differences as hypotheses and check them with real customer "
    "interviews or a small real survey.",
    "If a treatment difference matters to a decision, test it with real traffic (for example an "
    "A/B test on a landing page) before acting.",
    "Re-run with a different model and prompt wording; findings that change are artifacts, not insights.",
]


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def summary_points(a: dict[str, Any], comparison: dict[str, Any] | None = None) -> list[str]:
    pts: list[str] = []
    t = a["totals"]
    pts.append(
        f"{t['valid']} of {t['trials']} simulated responses were valid "
        f"({pct(1 - t['invalid_rate']) if t['invalid_rate'] is not None else 'n/a'} valid output)."
    )
    for tr in a["treatments"]:
        top = tr["top2box"]
        if top["share"] is not None:
            pts.append(
                f"{tr['label']}: {pct(top['share'])} ({top['n']} of {top['of']}) of simulated respondents "
                f"said probably or definitely (sampling variation {pct(top['ci_low'])} to "
                f"{pct(top['ci_high'])}); mean appeal {tr['appeal']['mean']:.1f} of 5."
            )
    for pair in (comparison or {}).get("pairs", []):
        if pair.get("diff") is None:
            continue
        verdict = (
            "a statistically detectable difference"
            if pair.get("significant")
            else "no statistically detectable difference"
        )
        pts.append(
            f"{pair['label']} versus {pair['vs']}: top-2-box differs by {pair['diff'] * 100:+.0f} points "
            f"(sampling variation {pair.get('diff_ci_low', 0) * 100:+.0f} to {pair.get('diff_ci_high', 0) * 100:+.0f} points where available; "
            f"Holm-adjusted p = {pair.get('p_holm', float('nan')):.3f}), {verdict} between simulated responses."
        )
    if a["objections"]:
        o = a["objections"][0]
        pts.append(
            f"The most common objection was '{o['code'].replace('_', ' ')}' ({pct(o['share'])} of valid responses)."
        )
    if a["benefits"]:
        b = a["benefits"][0]
        pts.append(
            f"The most common perceived benefit was '{b['code'].replace('_', ' ')}' ({pct(b['share'])})."
        )
    return pts


def build_report(
    session: Session, run_id: int, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if run is None:
        raise LookupError("no such run")
    analysis = concept.analyze(session, run_id)
    comparison = compare_mod.compare(session, run_id)
    manifest = run.manifest_json
    version = session.get(PopulationVersion, int(run.config_json.get("population_version_id", 0)))
    population = {
        "name": manifest.get("population", {}),
        "marginals": (version.diagnostics_json or {}).get("marginals", []) if version else [],
        "notes": "Population shares are generated from an assumed distribution.",
    }
    report: dict[str, Any] = {
        "title": f"{manifest.get('experiment', {}).get('name', run.name)}",
        "generated_at": datetime.now(UTC).isoformat(),
        "research_question": manifest.get("experiment", {}).get("research_question", ""),
        "hypothesis": manifest.get("experiment", {}).get("hypothesis", ""),
        "summary": summary_points(analysis, comparison),
        "analysis": analysis,
        "comparison": comparison,
        "population": population,
        "manifest": manifest,
        "limitations": LIMITATIONS,
        "follow_up": FOLLOW_UP,
        "run": {
            "id": run.id,
            "state": run.state,
            "done_units": run.done_units,
            "total_units": run.total_units,
        },
    }
    if extra:
        report.update(extra)
    return report


def _comparison_markdown(cmp: dict[str, Any]) -> list[str]:
    out = ["## Treatment comparison", ""]
    if not cmp.get("pairs"):
        return [*out, "Only one treatment, so there is nothing to compare.", ""]
    out += [
        "| Treatment | vs | Top-2-box | Baseline | Difference | Holm p | Cohen's h |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in cmp["pairs"]:
        if p.get("diff") is None:
            continue
        out.append(
            f"| {p['label']} | {p['vs']} | {pct(p['top2_treatment'])} | {pct(p['top2_baseline'])} "
            f"| {p['diff'] * 100:+.1f} pts | {p.get('p_holm', float('nan')):.3f} | {p['cohens_h']:.2f} |"
        )
    pricing = cmp.get("pricing")
    if pricing:
        out += ["", "Simulated purchase interest by price:", ""]
        out += [f"- ${r['price_usd']:g}: {pct(r['top2'])} (n={r['n']})" for r in pricing["curve"]]
        for v in pricing["monotone_violations"]:
            out.append(
                f"- Warning: interest was higher at ${v['higher_price']:g} than at ${v['lower_price']:g} "
                f"(p={v['p']:.3f}); an implausible pattern, treat it as a model artifact."
            )
        out.append(f"- {pricing['note']}")
    bal = cmp.get("balance")
    if bal:
        flag = " (IMBALANCED)" if bal["imbalanced"] else " (no detectable imbalance)"
        out += [
            "",
            f"Randomization balance: smallest Holm-adjusted p = {bal['min_p_holm']:.3f}{flag}",
        ]
    out += ["", *[f"_{n}_" for n in cmp.get("notes", [])], ""]
    return out


def render_markdown(r: dict[str, Any]) -> str:
    a = r["analysis"]
    m = r["manifest"]
    inf = m.get("inference", {})
    out = [
        f"# {r['title']}",
        "",
        "> Simulated results. Not observed human behavior and not a validated prediction.",
        "",
        "## Executive summary",
        "",
    ]
    out += [f"- {s}" for s in r["summary"]]
    out += ["", "## Research question", "", r["research_question"] or "(none)", ""]
    if r["hypothesis"]:
        out += ["**Hypothesis:** " + r["hypothesis"], ""]
    out += [
        "## Experiment configuration",
        "",
        f"- Treatments: {', '.join(t['label'] for t in m.get('experiment', {}).get('treatments', []))}",
        f"- Trials planned: {m.get('trials_planned')}  (valid {a['totals']['valid']})",
        f"- Prompt version: {m.get('prompt', {}).get('version')} ({m.get('prompt', {}).get('sha256_12')})",
        "",
        "## Inference model and runtime",
        "",
        f"- Runtime: {inf.get('runtime')} {inf.get('runtime_version') or ''}",
        f"- Model: {inf.get('model')} (digest {str(inf.get('model_digest'))[:12]}, quantization {inf.get('quantization')})",
        f"- Temperature {inf.get('temperature')}, seed {inf.get('seed')}, structured mode {inf.get('structured_mode')}",
        "",
        "## Simulated findings",
        "",
    ]
    for tr in a["treatments"]:
        out += [
            f"### {tr['label']} (n={tr['n_valid']})",
            "",
            "| Purchase intent | n | share |",
            "|---|---|---|",
        ]
        out += [
            f"| {i['code'].replace('_', ' ')} | {i['n']} | {pct(i['share'])} |"
            for i in tr["intent"]
        ]
        out += [""]
    out += _comparison_markdown(r.get("comparison") or {})
    out += [
        "## Segment analysis",
        "",
        "| Segment | Treatment | n | Top-2-box | Sampling variation |",
        "|---|---|---|---|---|",
    ]
    for s in a["segments"]:
        if s["suppressed"]:
            continue
        t2 = s["top2box"]
        out.append(
            f"| {s['attribute']}={s['value']} | {s['treatment_idx']} | {s['n']} | {pct(t2['share'])} | {pct(t2['ci_low'])} to {pct(t2['ci_high'])} |"
        )
    out += [
        "",
        f"_Segments with fewer than {concept.MIN_SEGMENT_N} valid responses are hidden._",
        "",
        "## Top objections",
        "",
    ]
    out += [
        f"- {o['code'].replace('_', ' ')}: {o['n']} ({pct(o['share'])})" for o in a["objections"]
    ] or ["- none recorded"]
    out += ["", "## Representative responses", ""]
    out += [
        f'- "{q["text"]}" ({q["kind"].replace("top_", "")}: {q["code"].replace("_", " ")}; source trial #{q["trial_id"]}, persona {q["persona_id"]})'
        for q in a["quotes"]
    ]
    out += ["", "## Contradictory patterns", ""]
    out += [f"- {c['description']} (n={c['n']})" for c in a["contradictions"]] or [
        "- none detected by the configured checks"
    ]
    out += ["", "## Limitations", ""] + [f"- {x}" for x in r["limitations"]]
    out += ["", "## Suggested real-world follow-up", ""] + [f"- {x}" for x in r["follow_up"]]
    out += [
        "",
        "## Reproducibility metadata",
        "",
        "```json",
        json.dumps(m, indent=2, default=str),
        "```",
        "",
    ]
    return "\n".join(out)


def render_html(r: dict[str, Any]) -> str:
    md = render_markdown(r)
    body = html.escape(md)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width, initial-scale=1"><title>{html.escape(r["title"])}</title>'
        "<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;"
        "line-height:1.5;color:#23201c;background:#f3efe9}pre{white-space:pre-wrap;font-family:ui-monospace,monospace;"
        "font-size:.9rem}</style></head><body><pre>" + body + "</pre></body></html>"
    )
