import json

from simulacra.benchmarks import workloads as wl
from simulacra.benchmarks.invariants import consistency_score, score_consistency
from simulacra.benchmarks.metrics import Sample, aggregate
from simulacra.benchmarks.personas import PERSONAS
from simulacra.benchmarks.schemas import OwnershipCheck, PurchaseDecision
from simulacra.inference.structured import validate_output
from simulacra.inference.types import GenerationResult


def test_workloads_are_deterministic_and_hashed() -> None:
    a1, a2 = wl.workload_b("m", 24), wl.workload_b("m", 24)
    assert wl.workload_hash(a1) == wl.workload_hash(a2)
    assert wl.workload_hash(a1) != wl.workload_hash(wl.workload_b("m", 25))
    assert wl.workload_hash(a1) != wl.workload_hash(wl.workload_b("other", 24))


def test_every_workload_builds_trials_with_schemas() -> None:
    for name, fn in wl.WORKLOADS.items():
        trials = fn("m", 6) if name not in ("F",) else fn("m", 1)
        assert trials, name
        assert all(t.request.messages and t.schema for t in trials)


def test_long_card_is_much_longer_than_short_card() -> None:
    p = PERSONAS[0]
    assert len(p.long_card()) > 4 * len(p.card())
    assert p.card() in p.long_card()
    assert "NO access to credit" in p.card()


def test_workload_f_covers_all_invariant_groups() -> None:
    groups = {t.group for t in wl.workload_f("m", reps=2)}
    assert groups == {
        "constraint",
        "price_sweep",
        "paraphrase",
        "instruction_conflict",
        "stability",
        "memory",
    }


def _sample(group: str, parsed: object, **extra: object) -> Sample:
    return Sample(0, group, "valid", GenerationResult(total_ms=1.0), {"parsed": parsed, **extra})


def _d(decision: str) -> PurchaseDecision:
    return PurchaseDecision(decision=decision, likelihood=3, reason_code="price", main_reason="x")


def test_budget_constraint_invariant_detects_violation() -> None:
    ok = [_sample("constraint", _d("pass")) for _ in range(3)]
    bad = [*ok, _sample("constraint", _d("buy_now"))]
    by_name = {d.name: d for d in score_consistency(ok)}
    assert by_name["budget_constraint"].value == 1.0 and by_name["budget_constraint"].passed
    by_name = {d.name: d for d in score_consistency(bad)}
    assert (
        by_name["budget_constraint"].value == 0.75 and by_name["budget_constraint"].passed is False
    )


def test_price_monotonicity_flags_rising_buy_rate() -> None:
    def sweep(rates: dict[int, int]) -> list[Sample]:
        out = []
        for price, buys in rates.items():
            for i in range(4):
                out.append(
                    _sample(
                        "price_sweep",
                        _d("buy_now" if i < buys else "pass"),
                        persona="p1",
                        price=price,
                    )
                )
        return out

    good = {d.name: d for d in score_consistency(sweep({50: 4, 200: 2, 800: 0}))}
    assert good["price_monotonicity"].passed
    bad = {d.name: d for d in score_consistency(sweep({50: 0, 200: 2, 800: 4}))}
    assert bad["price_monotonicity"].passed is False
    assert "rose" in bad["price_monotonicity"].detail


def test_paraphrase_and_stability_and_memory() -> None:
    para = []
    for style, buys in {"digits": 0, "words": 0, "sentence": 4}.items():
        for i in range(4):
            para.append(
                _sample(
                    "paraphrase", _d("buy_now" if i < buys else "pass"), persona="p1", style=style
                )
            )
    d = {x.name: x for x in score_consistency(para)}
    assert d["paraphrase_invariance"].passed is False  # spread 1.0

    stab = [_sample("stability", _d(x), persona="p2") for x in ("pass", "pass", "pass", "buy_now")]
    d = {x.name: x for x in score_consistency(stab)}
    assert d["repeated_trial_agreement"].value == 0.75
    assert d["repeated_trial_agreement"].kind == "stability"

    mem = [
        _sample("memory", OwnershipCheck(owns_similar_product=True, reason="r"), expected=True),
        _sample("memory", OwnershipCheck(owns_similar_product=False, reason="r"), expected=True),
    ]
    d = {x.name: x for x in score_consistency(mem)}
    assert d["memory_fact_recall"].value == 0.5


def test_consistency_score_ignores_missing_and_stability() -> None:
    assert consistency_score(score_consistency([])) is None


def test_decision_schema_rejects_out_of_range() -> None:
    status, _, _ = validate_output(
        json.dumps(
            {"decision": "buy_now", "likelihood": 9, "reason_code": "price", "main_reason": "x"}
        ),
        PurchaseDecision,
    )
    assert status == "schema_mismatch"


def _res(
    ms: float,
    tokens: int,
    ttft: float | None,
    decode_ms: float | None = None,
    error: str | None = None,
) -> GenerationResult:
    return GenerationResult(
        total_ms=ms, completion_tokens=tokens, ttft_ms=ttft, decode_ms=decode_ms, error=error
    )


def test_aggregate_prefers_runtime_reported_then_client_derived() -> None:
    rep = [Sample(i, "g", "valid", _res(1000, 100, 200, 500)) for i in range(4)]
    m = aggregate(rep, 2, 10.0)
    assert m.decode_tps_method == "runtime_reported" and m.decode_tokens_per_s_median == 200
    assert m.valid_trials_per_min == 24.0

    der = [Sample(i, "g", "valid", _res(1200, 100, 200)) for i in range(4)]
    m = aggregate(der, 1, 10.0)
    assert m.decode_tps_method == "client_derived" and m.decode_tokens_per_s_median == 100

    none = [Sample(0, "g", "valid", _res(100, 0, None))]
    assert aggregate(none, 1, 1.0).decode_tps_method == "unavailable"


def test_aggregate_failure_and_timeout_rates() -> None:
    samples = [
        Sample(0, "g", "valid", _res(100, 5, 10)),
        Sample(1, "g", "invalid_json", _res(100, 5, 10)),
        Sample(2, "g", "schema_mismatch", _res(100, 5, 10)),
        Sample(3, "g", "request_failed", _res(100, 0, None, error="ReadTimeout: x")),
    ]
    m = aggregate(samples, 1, 60.0)
    assert (m.valid_rate, m.invalid_json_rate, m.schema_mismatch_rate) == (0.25, 0.25, 0.25)
    assert m.failure_rate == 0.25 and m.timeout_rate == 0.25
    assert m.valid_trials_per_min == 1.0
