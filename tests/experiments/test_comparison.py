import json
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from simulacra.analysis import compare, stats
from simulacra.experiments import prompts, templates
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


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    url = f"sqlite:///{tmp_path / 'c.db'}"
    migrate.upgrade(url)
    return sessionmaker(make_engine(url), expire_on_commit=False)


def make_ab(
    sessions: sessionmaker[Session],
    rates: dict[int, float],
    n_per_arm: int = 80,
    design: str = "between",
    prices: dict[int, float] | None = None,
) -> int:
    """Deterministic trials: arm i has round(rates[i] * n) top-2-box responses."""
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
            size=n_per_arm * (1 if design == "within" else len(rates)),
            enrichment_json={},
            diagnostics_json={"marginals": []},
        )
        s.add(v)
        s.flush()
        total = n_per_arm if design == "within" else n_per_arm * len(rates)
        for i in range(total):
            s.add(
                PersonaRow(
                    version_id=v.id,
                    idx=i,
                    synthetic_id=f"P{i:04d}",
                    name="n",
                    attributes_json={"region": ["w", "s"][i % 2], "age": 20 + i % 50},
                    bio="b",
                    extras_json={},
                    meta_json={},
                )
            )
        exp = Experiment(
            name="E",
            kind="ad_comparison",
            research_question="q?",
            hypothesis="",
            population_version_id=v.id,
            scenario_json={},
            config_json={"design": design},
        )
        s.add(exp)
        s.flush()
        treatments = []
        for idx in rates:
            params = {"price_usd": prices[idx]} if prices else {"headline": f"H{idx}"}
            s.add(Treatment(experiment_id=exp.id, idx=idx, label=f"T{idx}", params_json=params))
            treatments.append({"idx": idx, "label": f"T{idx}", "params": params})
        run = Run(
            kind="experiment",
            name="E",
            state="completed",
            total_units=total,
            config_json={"experiment_id": exp.id, "population_version_id": v.id},
            manifest_json={"experiment": {"config": {"design": design}, "treatments": treatments}},
        )
        s.add(run)
        s.flush()
        for pos, idx in enumerate(rates):
            k = round(rates[idx] * n_per_arm)
            for j in range(n_per_arm):
                pid = f"P{j:04d}" if design == "within" else f"P{pos * n_per_arm + j:04d}"
                top = j < k
                s.add(
                    Trial(
                        run_id=run.id,
                        persona_id=pid,
                        treatment_idx=idx,
                        repeat_idx=0,
                        status="valid",
                        attempts=1,
                        prompt_text="p",
                        raw_output="o",
                        latency_ms=1.0,
                        created_at=1.0,
                        parsed_json={
                            "purchase_intent": "probably" if top else "probably_not",
                            "appeal": 4 if top else 2,
                            "top_benefit": "quality",
                            "top_objection": "none" if top else "price",
                            "reason": "r",
                        },
                    )
                )
        s.commit()
        return run.id


def test_between_comparison_matches_independent_math(sessions: sessionmaker[Session]) -> None:
    run_id = make_ab(sessions, {0: 0.25, 1: 0.5, 2: 0.26}, 80)
    with sessions() as s:
        c = compare.compare(s, run_id)
    assert c["design"] == "between" and [p["treatment_idx"] for p in c["pairs"]] == [1, 2]
    p1 = c["pairs"][0]
    assert (
        p1["top2_treatment"] == 0.5
        and p1["top2_baseline"] == 0.25
        and p1["diff"] == pytest.approx(0.25)
    )
    lo, hi = stats.newcombe_diff_ci(40, 80, 20, 80)
    assert (p1["diff_ci_low"], p1["diff_ci_high"]) == pytest.approx((lo, hi))
    assert p1["p"] == pytest.approx(stats.fisher_p(40, 80, 20, 80))
    assert p1["relative_lift"] == pytest.approx(1.0)
    # Holm over the two pairwise comparisons.
    adj = stats.holm_adjust([p["p"] for p in c["pairs"]])
    assert [p["p_holm"] for p in c["pairs"]] == pytest.approx(adj)
    assert c["pairs"][0]["significant"] and not c["pairs"][1]["significant"]
    assert p1["appeal"]["diff"] == pytest.approx(4 * 0.5 + 2 * 0.5 - (4 * 0.25 + 2 * 0.75))


def test_pairs_are_independent_of_trial_order_and_identical_baseline_used(
    sessions: sessionmaker[Session],
) -> None:
    run_id = make_ab(sessions, {0: 0.4, 1: 0.4}, 60)
    with sessions() as s:
        c = compare.compare(s, run_id)
    p = c["pairs"][0]
    assert (
        p["diff"] == 0 and p["p"] == pytest.approx(1.0) and not p["significant"]
    )  # A/A: nothing detected


def test_within_design_uses_paired_tests(sessions: sessionmaker[Session]) -> None:
    run_id = make_ab(sessions, {0: 0.3, 1: 0.6}, 50, design="within")
    with sessions() as s:
        c = compare.compare(s, run_id)
    p = c["pairs"][0]
    assert p["paired"] and p["n_treatment"] == 50 and c["segments"] == [] and c["balance"] is None
    # Persona j is top-2-box in arm 0 iff j < 15 and in arm 1 iff j < 30: 15 discordant, all arm-1-only.
    assert p["discordant"] == {"treatment_only": 15, "baseline_only": 0}
    assert p["p"] == pytest.approx(stats.mcnemar_exact_p(15, 0))


def test_balance_and_segments_are_reported_with_exploratory_label(
    sessions: sessionmaker[Session],
) -> None:
    run_id = make_ab(sessions, {0: 0.25, 1: 0.5}, 100)
    with sessions() as s:
        c = compare.compare(s, run_id)
    assert c["balance"]["arm_sizes"] == {"0": 100, "1": 100}
    assert all("p_holm" in x for x in c["balance"]["checks"])
    assert c["segments"] and all(
        seg["n_treatment"] >= compare.MIN_ARM_N and seg["n_baseline"] >= compare.MIN_ARM_N
        for seg in c["segments"]
    )
    assert any("exploratory" in n for n in c["notes"])


def test_pricing_curve_and_monotonicity_violation(sessions: sessionmaker[Session]) -> None:
    ok = make_ab(sessions, {0: 0.6, 1: 0.4, 2: 0.2}, 80, prices={0: 49, 1: 79, 2: 129})
    bad = make_ab(sessions, {0: 0.2, 1: 0.5, 2: 0.8}, 80, prices={0: 49, 1: 79, 2: 129})
    with sessions() as s:
        good_c, bad_c = compare.compare(s, ok), compare.compare(s, bad)
    assert [r["price_usd"] for r in good_c["pricing"]["curve"]] == [49, 79, 129]
    assert good_c["pricing"]["monotone_violations"] == []
    assert len(bad_c["pricing"]["monotone_violations"]) == 2
    with sessions() as s:
        md = build.render_markdown(build.build_report(s, bad))
    assert (
        "Warning: interest was higher at $79" in md and "not real demand" in md.lower()
    ) or "Not real demand" in md


def test_single_treatment_has_nothing_to_compare(sessions: sessionmaker[Session]) -> None:
    run_id = make_ab(sessions, {0: 0.5}, 20)
    with sessions() as s:
        c = compare.compare(s, run_id)
    assert c["pairs"] == [] and "nothing to compare" in c["notes"][0]


def test_report_includes_comparison_section(sessions: sessionmaker[Session]) -> None:
    run_id = make_ab(sessions, {0: 0.25, 1: 0.5}, 80)
    with sessions() as s:
        report = build.build_report(s, run_id)
    md = build.render_markdown(report)
    assert "## Treatment comparison" in md and "Holm" in md and "Randomization balance" in md
    assert any("T1 versus T0" in line and "Holm-adjusted p" in line for line in report["summary"])
    assert json.dumps(report, default=str)


def test_templates_validate_inputs() -> None:
    arms = templates.ad_comparison(["Save time", "Save money"])
    assert [a.label for a in arms] == ["Headline A", "Headline B"] and arms[1].params == {
        "headline": "Save money"
    }
    with pytest.raises(ValueError):
        templates.ad_comparison(["only one"])
    with pytest.raises(ValueError):
        templates.ad_comparison(["a", "  "])
    p = templates.pricing([49.0, 79.5])
    assert [x.label for x in p] == ["$49", "$79.5"] and p[0].params == {"price_usd": 49}
    for bad in ([49.0], [49.0, 49.0], [-1.0, 5.0]):
        with pytest.raises(ValueError):
            templates.pricing(bad)


def test_treatment_isolation_in_prompts() -> None:
    """A persona only ever sees their own treatment's text."""
    scenario = {"product_name": "Mug", "description": "A self-heating mug for tea and coffee."}
    arms = [{"headline": f"UNIQUEHEADLINE{i}"} for i in range(4)]
    texts = [
        prompts.flatten(prompts.build_messages(scenario, arm, "Sam (P1)\n- age: 30"))
        for arm in arms
    ]
    for i, text in enumerate(texts):
        assert f"UNIQUEHEADLINE{i}" in text
        assert not any(f"UNIQUEHEADLINE{j}" in text for j in range(4) if j != i)
    price_arms = [{"price_usd": p} for p in (11.11, 22.22, 33.33)]
    ptexts = [prompts.flatten(prompts.build_messages(scenario, a, "Sam")) for a in price_arms]
    for i, text in enumerate(ptexts):
        others = [f"${p}" for j, p in enumerate((11.11, 22.22, 33.33)) if j != i]
        assert not any(o in text for o in others)
    assert Counter(len(t) > 0 for t in texts) == {True: 4}


def test_comparison_uses_only_first_repeat_and_stability_is_reported(
    sessions: sessionmaker[Session],
) -> None:
    from simulacra.analysis import concept

    run_id = make_ab(sessions, {0: 0.5, 1: 0.5}, 40)
    with sessions() as s:
        run = s.get(Run, run_id)
        assert run is not None
        # Add a contradictory second repeat for every trial: if it leaked into the test, the counts change.
        for t in list(s.query(Trial).filter(Trial.run_id == run_id)):
            flipped = dict(t.parsed_json or {})
            flipped["purchase_intent"] = (
                "probably_not" if flipped["purchase_intent"] == "probably" else "probably"
            )
            s.add(
                Trial(
                    run_id=run_id,
                    persona_id=t.persona_id,
                    treatment_idx=t.treatment_idx,
                    repeat_idx=1,
                    status="valid",
                    attempts=1,
                    prompt_text="p",
                    raw_output="o",
                    parsed_json=flipped,
                    latency_ms=1.0,
                    created_at=1.0,
                )
            )
        s.commit()
        c = compare.compare(s, run_id)
        a = concept.analyze(s, run_id)
    assert c["pairs"][0]["n_treatment"] == 40 and c["pairs"][0]["diff"] == 0  # first repeats only
    assert any("first repeat" in n for n in c["notes"])
    stab = a["repeat_stability"]
    assert (
        stab["personas_with_repeats"] == 80 and stab["top2_agreement"] == 0.0
    )  # every repeat flipped
    assert concept.analyze(s, make_ab(sessions, {0: 0.5}, 10))["repeat_stability"] is None
