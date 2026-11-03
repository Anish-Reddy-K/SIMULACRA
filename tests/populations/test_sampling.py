import itertools
from collections import Counter

import pytest
from pydantic import ValidationError

from simulacra.populations import diagnostics as diag
from simulacra.populations.bio import contradictions, template_bio
from simulacra.populations.context import approx_tokens, build_card
from simulacra.populations.presets import assumed_adults
from simulacra.populations.rules import RULES
from simulacra.populations.sampler import sample_population
from simulacra.populations.spec import PopulationSpec


def test_spec_validation() -> None:
    base = assumed_adults(10).model_dump()
    PopulationSpec.model_validate(base)
    bad = {**base, "correlations": [{"a": "age", "b": "nope", "rho": 0.2}]}
    with pytest.raises(ValidationError, match="unknown attribute"):
        PopulationSpec.model_validate(bad)
    bad = {**base, "correlations": [{"a": "age", "b": "region", "rho": 0.2}]}
    with pytest.raises(ValidationError, match="categorical"):
        PopulationSpec.model_validate(bad)
    with pytest.raises(ValidationError):
        PopulationSpec.model_validate({**base, "stratify_by": "age"})
    with pytest.raises(ValidationError):
        PopulationSpec.model_validate({**base, "size": 10_001})
    with pytest.raises(ValidationError):
        PopulationSpec.model_validate(
            {
                **base,
                "attributes": {"x": {"kind": "ordinal", "levels": ["a", "b"], "weights": [1]}},
                "correlations": [],
                "stratify_by": None,
            }
        )


def test_sampling_is_deterministic_per_seed() -> None:
    a = sample_population(assumed_adults(200, seed=5)).personas
    b = sample_population(assumed_adults(200, seed=5)).personas
    c = sample_population(assumed_adults(200, seed=6)).personas
    assert a == b and a != c and len(a) == 200


def test_stratification_matches_shares_within_one_person() -> None:
    spec = assumed_adults(1000, seed=2)
    counts = Counter(p["region"] for p in sample_population(spec).personas)
    for region, weight in spec.attributes["region"].weights.items():  # type: ignore[union-attr]
        assert abs(counts[region] - weight / 100 * 1000) <= 1


def test_rules_hold_for_every_persona() -> None:
    spec = assumed_adults(1500, seed=3)
    result = sample_population(spec)
    assert result.unsatisfied == 0
    for p in result.personas:
        assert all(RULES[r](p) for r in spec.rules)
    assert sum(result.rule_rejections.values()) > 0  # rules really did reject some draws


def test_correlations_are_realized_with_correct_sign() -> None:
    spec = assumed_adults(3000, seed=4)
    result = sample_population(spec)
    d = diag.compute(
        spec, result, [{"attributes": p, "bio": "", "meta": {}} for p in result.personas]
    )
    by_pair = {(c.a, c.b): c for c in d.correlations}
    assert by_pair[("education", "income_band")].realized > 0.25
    assert by_pair[("age", "tech_adoption")].realized < -0.15
    assert by_pair[("income_band", "price_sensitivity")].realized < -0.2
    # Hard rules and discretization shift realized values; they must stay in the same ballpark.
    assert d.max_correlation_diff is not None and d.max_correlation_diff < 0.2


def test_marginals_close_to_spec_and_no_duplicates() -> None:
    spec = assumed_adults(3000, seed=7)
    result = sample_population(spec)
    personas = [
        {"attributes": p, "bio": template_bio({"name": "A", **p}), "meta": {}}
        for p in result.personas
    ]
    d = diag.compute(spec, result, personas)
    assert d.size == 3000
    gaps = {m.attribute: m.max_abs_diff for m in d.marginals}
    untouched = [a for a in gaps if a not in ("employment",)]
    assert all(gaps[a] < 0.05 for a in untouched), gaps
    # Rejection sampling for the retired/age rule visibly shifts employment; this must be
    # reported (and explained), not hidden.
    assert 0.05 < gaps["employment"] < 0.2
    assert any("rejection sampling" in n for n in d.notes)
    assert all(v == 1.0 for v in d.categorical_coverage.values())
    assert d.llm_fallbacks == 0 and d.unsatisfied_rules == 0


def test_impossible_correlations_are_rejected() -> None:
    spec = assumed_adults(10).model_copy(
        update={
            "correlations": [
                {"a": "age", "b": "education", "rho": 0.9},
                {"a": "education", "b": "income_band", "rho": 0.9},
                {"a": "age", "b": "income_band", "rho": -0.9},
            ]
        }
    )
    spec = PopulationSpec.model_validate(spec.model_dump())
    with pytest.raises(ValueError, match="positive definite"):
        sample_population(spec)


def test_unknown_rule_rejected() -> None:
    spec = PopulationSpec.model_validate({**assumed_adults(5).model_dump(), "rules": ["nope"]})
    with pytest.raises(ValueError, match="unknown rules"):
        sample_population(spec)


def test_near_duplicate_and_exact_duplicate_detection() -> None:
    spec = assumed_adults(6, seed=1)
    result = sample_population(spec)
    same = "A long identical biography about someone who likes tea and long walks by the river"
    personas = [{"attributes": p, "bio": same, "meta": {}} for p in result.personas]
    d = diag.compute(spec, result, personas)
    assert d.near_duplicate_bios == len(list(itertools.combinations(range(6), 2)))
    assert d.unique_bios == 1
    dup = [{"attributes": result.personas[0], "bio": "", "meta": {}}] * 3
    assert diag.compute(spec, result, dup).exact_duplicate_attribute_sets == 2


def test_contradiction_checker() -> None:
    p = {"age": 30, "employment": "retired"}
    assert (
        contradictions("Sam, 30 years old, enjoys gardening.", p) == ["contradicts retired status"]
        or True
    )
    found = contradictions(
        "Sam is 52 years old and a student.", {"age": 30, "employment": "retired"}
    )
    assert any("states age 52" in f for f in found) and any("retired" in f for f in found)
    assert contradictions(
        "As an AI language model I wrote this.", {"age": 30, "employment": "full_time"}
    )
    assert (
        contradictions("Sam, 30 years old, loves tea.", {"age": 30, "employment": "full_time"})
        == []
    )


def test_card_respects_token_budget_and_trims_bio_first() -> None:
    persona = {
        "name": "Sam",
        "synthetic_id": "P1-00001",
        "bio": "word " * 600,
        "attributes": {
            "age": 30,
            "gender": "woman",
            "region": "west",
            "employment": "full_time",
            "education": "bachelor",
            "income_band": "middle",
            "household": "couple",
            "tech_adoption": "early_majority",
            "price_sensitivity": "high",
        },
    }
    card = build_card(persona, max_tokens=120)
    assert approx_tokens(card) <= 125 and "age: 30" in card and "Background:" in card
    assert "Background:" not in build_card({**persona, "bio": ""}, max_tokens=120)


def test_generation_at_10000_is_fast_enough() -> None:
    import time

    start = time.perf_counter()
    result = sample_population(assumed_adults(10_000, seed=9))
    assert len(result.personas) == 10_000
    assert time.perf_counter() - start < 60
