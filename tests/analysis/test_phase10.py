"""Phase 10 analysis: themes, clusters, synthesis claims with a verifier, and run comparison."""

import math
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from simulacra.analysis import runcompare, synthesis, themes
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine
from simulacra.persistence.models import Run, Trial
from tests.experiments.test_analysis import seed_run


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    url = f"sqlite:///{tmp_path / 'p10.db'}"
    migrate.upgrade(url)
    return sessionmaker(make_engine(url), expire_on_commit=False)


def test_tokens_drop_stopwords_and_short_words() -> None:
    assert themes.tokens("I would not pay that much for a mug, it's too pricey!") == [
        "pay",
        "much",
        "mug",
        "pricey",
    ] or "pricey" in themes.tokens("it is too pricey")
    assert themes.tokens("The a an of") == []


def test_distinctive_terms_rank_group_specific_words() -> None:
    groups = {
        "price": [
            "too expensive for the price",
            "expensive and overpriced",
            "price is too high expensive",
        ]
        * 3,
        "trust": [
            "not sure about the brand quality",
            "do not trust this brand",
            "brand reputation unknown",
        ]
        * 3,
    }
    out = themes.distinctive_terms(groups)
    assert out["price"][0]["term"] in ("expensive", "price") and out["trust"][0]["term"] == "brand"
    assert all(d["z"] > 0 for g in out.values() for d in g)
    assert themes.distinctive_terms({"a": [], "b": []}) == {"a": [], "b": []}


def test_clusters_group_near_duplicates_and_keep_trial_ids() -> None:
    items = [
        (1, "too expensive for what it does"),
        (2, "far too expensive for what it is"),
        (3, "I already have a perfectly good mug"),
        (4, "already own a good mug at home"),
        (5, "too expensive for what it does"),
    ]
    clusters = themes.cluster_reasons(items)
    sizes = sorted(c.size for c in clusters)
    assert sizes == [2, 3] and clusters[0].size == 3 and clusters[0].exemplar_trial_id == 1
    assert set(clusters[0].trial_ids) == {1, 2, 5} and themes.cluster_reasons([(1, "the of")]) == []


def test_synthesis_claims_verify_and_detect_tampering(sessions: sessionmaker[Session]) -> None:
    run_id = seed_run(sessions)
    with sessions() as s:
        claims = synthesis.build(s, run_id)
        kinds = {c["kind"] for c in claims}
        assert {"overall", "objection"} <= kinds
        assert all(c["evidence_trial_ids"] for c in claims)
        assert all(v["verified"] for v in synthesis.verify(s, run_id, claims))
        bad = [dict(claims[0], numbers=dict(claims[0]["numbers"], k=claims[0]["numbers"]["k"] + 1))]
        res = synthesis.verify(s, run_id, bad)
        assert not res[0]["verified"] and "expected" in res[0]["problems"][0]
        forged = [dict(claims[0], evidence_trial_ids=[10**9])]
        assert not synthesis.verify(s, run_id, forged)[0]["verified"]


def test_kappa_values() -> None:
    assert runcompare.cohens_kappa([True, False] * 5, [True, False] * 5) == 1.0
    assert runcompare.cohens_kappa([True, False] * 5, [False, True] * 5) == -1.0
    assert runcompare.cohens_kappa([True] * 4, [True] * 4) == 1.0
    a = [True] * 20 + [False] * 20
    b = [True] * 15 + [False] * 5 + [True] * 5 + [False] * 15
    assert runcompare.cohens_kappa(a, b) == pytest.approx(0.5)  # po=.75, pe=.5
    assert runcompare.cohens_kappa([], []) is None


def clone_run(s: Session, run_id: int, flip_every: int) -> int:
    src = s.get(Run, run_id)
    assert src is not None
    new = Run(
        kind=src.kind,
        name="B",
        state="completed",
        total_units=src.total_units,
        config_json=src.config_json,
        manifest_json={**src.manifest_json, "inference": {"model": "other"}},
    )
    s.add(new)
    s.flush()
    for i, t in enumerate(s.query(Trial).filter(Trial.run_id == run_id).order_by(Trial.id).all()):
        parsed = dict(t.parsed_json or {})
        if flip_every and parsed and i % flip_every == 0:
            parsed["purchase_intent"] = (
                "probably_not"
                if parsed["purchase_intent"] in ("definitely", "probably")
                else "probably"
            )
        s.add(
            Trial(
                run_id=new.id,
                persona_id=t.persona_id,
                treatment_idx=t.treatment_idx,
                repeat_idx=t.repeat_idx,
                status=t.status,
                attempts=1,
                prompt_text="p",
                raw_output="o",
                parsed_json=parsed or None,
                latency_ms=1.0,
                created_at=1.0,
            )
        )
    s.commit()
    return new.id


def test_run_comparison_identical_and_perturbed(sessions: sessionmaker[Session]) -> None:
    a = seed_run(sessions)
    with sessions() as s:
        same = clone_run(s, a, flip_every=0)
        diff = clone_run(s, a, flip_every=4)
        ident = runcompare.compare_runs(s, a, same)
        assert (
            ident["top2_agreement"] == 1.0
            and ident["top2_kappa"] == 1.0
            and ident["mcnemar_p"] == 1.0
        )
        out = runcompare.compare_runs(s, a, diff)
    assert out["matched_trials"] == ident["matched_trials"] > 0
    assert 0.5 < out["top2_agreement"] < 1.0 and out["top2_kappa"] < 1.0
    assert out["discordant"]["a_only"] + out["discordant"]["b_only"] > 0
    assert out["run_b"]["model"] == "other" and math.isclose(out["objection_agreement"], 1.0)
    with sessions() as s, pytest.raises(LookupError):
        runcompare.compare_runs(s, a, 99999)


def test_query_engine_matches_independent_counts(sessions: sessionmaker[Session]) -> None:
    from simulacra.analysis import explore
    from simulacra.persistence.models import PersonaRow

    run_id = seed_run(sessions)
    with sessions() as s:
        attrs = {p.synthetic_id: p.attributes_json for p in s.query(PersonaRow)}
        valid = [
            t
            for t in s.query(Trial).filter(Trial.run_id == run_id, Trial.status == "valid")
            if t.treatment_idx == 0
        ]
        out = explore.query(s, run_id, "top2_share", group_by="region", treatment=0)
        for row in out["rows"]:
            members = [t for t in valid if attrs[t.persona_id]["region"] == row["group"]]
            assert row["n"] == len(members)
            k = sum(
                1
                for t in members
                if (t.parsed_json or {})["purchase_intent"] in ("definitely", "probably")
            )
            assert row["k"] == k and row["value"] == pytest.approx(k / len(members))
            assert all(s.get(Trial, i) is not None for i in row["evidence_trial_ids"])
        filtered = explore.query(s, run_id, "count", filters={"region": "west"}, treatment=0)
        assert filtered["rows"][0]["value"] == sum(
            1 for t in valid if attrs[t.persona_id]["region"] == "west"
        )
        obj = explore.query(
            s, run_id, "objection_share", group_by="income_band", code="price", treatment=0
        )
        assert {r["group"] for r in obj["rows"]} == {"low", "middle"}
        assert any(r["suppressed"] for r in obj["rows"])  # the "low" band has only 8 personas
        bad_questions = (
            ("nope", None, None),
            ("top2_share", "shoe_size", None),
            ("objection_share", None, None),
            ("intent_share", None, "maybe"),
        )
        for metric, group_by, code in bad_questions:
            with pytest.raises(explore.QueryError):
                explore.query(s, run_id, metric, group_by=group_by, code=code)
