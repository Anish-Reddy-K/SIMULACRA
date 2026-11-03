"""The claim audit: every statistic in the analysis and report is recomputed independently
from the raw trial rows with separate, simple code, and must match."""

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from simulacra.analysis import concept
from simulacra.experiments.assign import assign_treatment, trial_seed
from simulacra.experiments.service import plan_units
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine
from simulacra.persistence.models import (
    Experiment,
    PersonaRow,
    Population,
    PopulationVersion,
    Run,
    Treatment,
    Trial,
)
from simulacra.reporting import build


def pj(t: Trial) -> dict[str, Any]:
    return t.parsed_json or {}


INTENTS = ["definitely", "probably", "unsure", "probably_not", "definitely_not"]
OBJ = ["price", "trust", "need", "none", "other"]


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    url = f"sqlite:///{tmp_path / 'a.db'}"
    migrate.upgrade(url)
    return sessionmaker(make_engine(url), expire_on_commit=False)


def seed_run(sessions: sessionmaker[Session], n_personas: int = 60) -> int:
    """A run with deterministic, varied trials across two treatments and several segments."""
    with sessions() as s:
        pop = Population(name="p")
        s.add(pop)
        s.flush()
        v = PopulationVersion(
            population_id=pop.id,
            version=1,
            status="ready",
            source="generated",
            spec_json={},
            seed=1,
            size=n_personas,
            enrichment_json={},
            diagnostics_json={"marginals": []},
        )
        s.add(v)
        s.flush()
        for i in range(n_personas):
            s.add(
                PersonaRow(
                    version_id=v.id,
                    idx=i,
                    synthetic_id=f"P{i:03d}",
                    name=f"N{i}",
                    attributes_json={
                        "age": 20 + (i * 7) % 60,
                        "region": ["west", "south"][i % 2],
                        "income_band": "low" if i < 8 else "middle",
                    },
                    bio="b",
                    extras_json={},
                    meta_json={},
                )
            )
        exp = Experiment(
            name="E",
            kind="product_concept",
            research_question="q?",
            hypothesis="h",
            population_version_id=v.id,
            scenario_json={"product_name": "X"},
            config_json={},
        )
        s.add(exp)
        s.flush()
        s.add_all(
            [
                Treatment(experiment_id=exp.id, idx=0, label="A", params_json={}),
                Treatment(experiment_id=exp.id, idx=1, label="B", params_json={}),
            ]
        )
        run = Run(
            kind="experiment",
            name="E",
            state="completed",
            total_units=n_personas * 2,
            config_json={"experiment_id": exp.id, "population_version_id": v.id},
            manifest_json={
                "experiment": {
                    "name": "E",
                    "research_question": "q?",
                    "hypothesis": "h",
                    "treatments": [{"label": "A"}, {"label": "B"}],
                },
                "inference": {},
                "prompt": {},
                "trials_planned": n_personas * 2,
            },
        )
        s.add(run)
        s.flush()
        for i in range(n_personas):
            for t in (0, 1):
                k = (i * 3 + t * 5) % 11
                status = "valid" if k != 10 else "invalid_json"
                parsed = (
                    None
                    if status != "valid"
                    else {
                        "purchase_intent": INTENTS[(i + t * 2) % 5],
                        "appeal": 1 + (i + t) % 5,
                        "top_benefit": "saves_time" if i % 3 else "quality",
                        "top_objection": OBJ[(i + t) % 5],
                        "reason": f"reason {i}-{t}",
                    }
                )
                s.add(
                    Trial(
                        run_id=run.id,
                        persona_id=f"P{i:03d}",
                        treatment_idx=t,
                        repeat_idx=0,
                        status=status,
                        attempts=1,
                        prompt_text="p",
                        raw_output="o",
                        parsed_json=parsed,
                        latency_ms=1.0,
                        created_at=1.0,
                    )
                )
        s.commit()
        return run.id


def test_wilson_matches_known_values() -> None:
    lo, hi = concept.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    assert concept.wilson(0, 0) == (0.0, 0.0)
    lo, hi = concept.wilson(0, 10)
    assert lo == 0.0 and 0.25 < hi < 0.32


def test_age_band() -> None:
    assert [concept.age_band(a) for a in (18, 29, 30, 44, 45, 59, 60, 90)] == [
        "18-29",
        "18-29",
        "30-44",
        "30-44",
        "45-59",
        "45-59",
        "60+",
        "60+",
    ]


def test_claim_audit_headline_numbers(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        a = concept.analyze(s, run_id)
        trials = list(s.query(Trial).filter(Trial.run_id == run_id))
    assert a["totals"]["trials"] == 120 == len(trials)
    valid = [t for t in trials if t.status == "valid"]
    assert a["totals"]["valid"] == len(valid)
    assert a["totals"]["invalid_rate"] == pytest.approx((120 - len(valid)) / 120)

    for tr in a["treatments"]:
        rows = [t for t in valid if t.treatment_idx == tr["idx"]]
        n = len(rows)
        assert tr["n_valid"] == n
        top = sum(1 for t in rows if pj(t)["purchase_intent"] in ("definitely", "probably"))
        assert tr["top2box"]["n"] == top and tr["top2box"]["of"] == n
        assert tr["top2box"]["share"] == pytest.approx(top / n)
        assert tr["appeal"]["mean"] == pytest.approx(sum(pj(t)["appeal"] for t in rows) / n)
        counts = Counter(pj(t)["purchase_intent"] for t in rows)
        for item in tr["intent"]:
            assert item["n"] == counts.get(item["code"], 0)
        assert sum(i["n"] for i in tr["intent"]) == n
        lo, hi = concept.wilson(top, n)
        assert tr["top2box"]["ci_low"] == pytest.approx(lo) and tr["top2box"][
            "ci_high"
        ] == pytest.approx(hi)


def test_claim_audit_segments_and_suppression(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        a = concept.analyze(s, run_id)
        trials = list(s.query(Trial).filter(Trial.run_id == run_id))
        attrs = {p.synthetic_id: p.attributes_json for p in s.query(PersonaRow)}
    valid = [t for t in trials if t.status == "valid"]
    checked = 0
    for seg in a["segments"]:
        if seg["attribute"] == "age_band":
            members = [
                t
                for t in valid
                if t.treatment_idx == seg["treatment_idx"]
                and concept.age_band(attrs[t.persona_id]["age"]) == seg["value"]
            ]
        else:
            members = [
                t
                for t in valid
                if t.treatment_idx == seg["treatment_idx"]
                and str(attrs[t.persona_id][seg["attribute"]]) == seg["value"]
            ]
        assert seg["n"] == len(members)
        assert seg["suppressed"] == (len(members) < concept.MIN_SEGMENT_N)
        if not seg["suppressed"]:
            top = sum(1 for t in members if pj(t)["purchase_intent"] in ("definitely", "probably"))
            assert seg["top2box"]["n"] == top
            checked += 1
        else:
            assert "top2box" not in seg  # suppressed segments expose no numbers
    assert checked > 0 and any(s["suppressed"] for s in a["segments"])


def test_quotes_link_to_real_trials_with_matching_text(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        a = concept.analyze(s, run_id)
        assert a["quotes"]
        for q in a["quotes"]:
            t = s.get(Trial, q["trial_id"])
            assert t is not None and t.run_id == run_id and t.persona_id == q["persona_id"]
            assert pj(t)["reason"] == q["text"]
            field = q["kind"]
            assert pj(t)[field] == q["code"]


def test_contradictions_are_detected_and_reproducible(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        a1 = concept.analyze(s, run_id)
        a2 = concept.analyze(s, run_id)
        assert a1 == a2  # deterministic
        odd = [c for c in a1["contradictions"] if c["kind"] == "high_appeal_low_intent"]
        trials = [t for t in s.query(Trial).filter(Trial.run_id == run_id) if t.status == "valid"]
        expected = sum(
            1
            for t in trials
            if pj(t)["appeal"] >= 4
            and pj(t)["purchase_intent"] in ("probably_not", "definitely_not")
        )
        if expected:
            assert odd and odd[0]["n"] == expected
            assert all(s.get(Trial, i) is not None for i in odd[0]["example_trial_ids"])


def test_report_numbers_match_analysis_and_markdown_is_complete(
    sessions: sessionmaker[Session],
) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        report = build.build_report(s, run_id)
    md = build.render_markdown(report)
    for heading in (
        "Executive summary",
        "Research question",
        "Experiment configuration",
        "Inference model and runtime",
        "Simulated findings",
        "Segment analysis",
        "Top objections",
        "Representative responses",
        "Contradictory patterns",
        "Limitations",
        "Suggested real-world follow-up",
        "Reproducibility metadata",
    ):
        assert f"## {heading}" in md
    assert "Not observed human behavior" in md or "not observed human behavior" in md
    # Every percentage in the executive summary must be derivable from the analysis numbers.
    a = report["analysis"]
    allowed = {
        round(x * 100)
        for tr in a["treatments"]
        for x in [tr["top2box"]["share"], tr["top2box"]["ci_low"], tr["top2box"]["ci_high"]]
        if x is not None
    }
    allowed |= {round((1 - a["totals"]["invalid_rate"]) * 100)}
    allowed |= {round(o["share"] * 100) for o in a["objections"][:1] + a["benefits"][:1]}
    for line in report["summary"]:
        for num in re.findall(r"(\d+)%", line):
            assert int(num) in allowed, (line, num)
    html = build.render_html(report)
    assert "<script" not in html and html.startswith("<!doctype html>")


def test_report_html_escapes_untrusted_text(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        t = s.query(Trial).filter(Trial.run_id == run_id, Trial.status == "valid").first()
        assert t is not None and t.parsed_json is not None
        t.parsed_json = {
            **t.parsed_json,
            "reason": "<script>alert(1)</script>",
            "top_objection": "price",
            "top_benefit": "quality",
        }
        s.commit()
        report = build.build_report(s, run_id)
    out = build.render_html({**report, "title": "<img src=x onerror=1>"})
    assert "<script>alert(1)</script>" not in out and "&lt;script&gt;" in out
    assert "<img src=x" not in out


def test_assignment_is_stable_balanced_and_order_independent() -> None:
    ids = [f"P{i:04d}" for i in range(4000)]
    a = [assign_treatment(7, p, 3) for p in ids]
    b = [assign_treatment(7, p, 3) for p in reversed(ids)][::-1]
    assert a == b  # independent of order
    counts = Counter(a)
    assert all(abs(c - 4000 / 3) < 150 for c in counts.values())
    assert a != [assign_treatment(8, p, 3) for p in ids]  # seed matters
    assert trial_seed(1, "P1", 0, 0) == trial_seed(1, "P1", 0, 0)
    assert len({trial_seed(1, "P1", t, r) for t in range(3) for r in range(3)}) == 9


def test_plan_units_between_and_within() -> None:
    ids = [f"P{i}" for i in range(100)]
    between = plan_units(ids, 3, "between", 2, seed=1)
    assert len(between) == 200 and [u["idx"] for u in between] == list(range(200))
    assert len({(u["persona_id"], u["treatment_idx"], u["repeat_idx"]) for u in between}) == 200
    per_persona = Counter(u["persona_id"] for u in between)
    assert set(per_persona.values()) == {2}  # one arm x two repeats
    within = plan_units(ids, 3, "within", 1, seed=1)
    assert len(within) == 300
    assert math.isclose(len(plan_units(ids, 3, "between", 1, seed=1)), 100)
