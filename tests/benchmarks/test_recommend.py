"""Policy tests use hand-written evidence fixtures. They verify the rules, not real hardware."""

from simulacra.benchmarks.policy import Policy
from simulacra.benchmarks.recommend import (
    ConfigEvidence,
    SoakEvidence,
    parameter_billions,
    recommend,
)

RAM = 16384.0


def ev(
    label: str,
    tpm: float = 60.0,
    valid: float = 1.0,
    cons: float | None = 0.9,
    mem: float | None = 3000.0,
    **kw: object,
) -> ConfigEvidence:
    base: dict[str, object] = dict(
        key=label,
        label=label,
        runtime_kind="ollama",
        runtime_version="1",
        base_url="http://127.0.0.1:11434",
        model=label,
        quantization=None,
        parameter_b=3.0,
        structured_mode="constrained",
        evidence="detailed",
        compat_ok=True,
        valid_per_min=tpm,
        best_concurrency=4,
        valid_rate=valid,
        failure_rate=0.0,
        peak_rss_mb=mem,
        min_available_mb=2000.0,
        swap_growth_mb=0.0,
        consistency=cons,
    )
    base.update(kw)
    return ConfigEvidence(**base)


def test_nothing_measured_recommends_nothing() -> None:
    rec = recommend("fastest", [], Policy(), RAM)
    assert rec.selected is None and "Run a benchmark" in rec.rationale[0]


def test_fastest_picks_highest_throughput_and_lists_others() -> None:
    rec = recommend("fastest", [ev("slow", 30), ev("fast", 90), ev("mid", 60)], Policy(), RAM)
    assert rec.selected and rec.selected.label == "fast"
    assert [c.label for c in rec.considered if c.status in ("selected", "ranked")] == [
        "fast",
        "mid",
        "slow",
    ]


def test_exclusions_have_reasons() -> None:
    items = [
        ev("ok", 50),
        ev("hungry", 100, mem=12000),
        ev("flaky", 100, valid=0.5),
        ev("swappy", 100, swap_growth_mb=3000.0),
        ev("broken", compat_ok=False, valid_per_min=None, compat_error="no response"),
    ]
    rec = recommend("fastest", items, Policy(), RAM)
    assert rec.selected and rec.selected.label == "ok"
    reasons = {c.label: c.detail for c in rec.considered if c.status == "excluded"}
    assert "peak memory" in reasons["hungry"] and "valid structured-output" in reasons["flaky"]
    assert "swap" in reasons["swappy"] and "compatibility" in reasons["broken"]


def test_unbenchmarked_is_labeled_never_ranked() -> None:
    rec = recommend("fastest", [ev("measured", 40), ev("blank", valid_per_min=None)], Policy(), RAM)
    assert rec.selected and rec.selected.label == "measured"
    assert any(c.label == "blank" and c.status == "not_benchmarked" for c in rec.considered)


def test_balanced_uses_documented_weights() -> None:
    fast_sloppy = ev("fast_sloppy", 100, valid=0.92, cons=0.5)
    steady = ev("steady", 70, valid=1.0, cons=0.95)
    rec = recommend("balanced", [fast_sloppy, steady], Policy(), RAM)
    assert rec.selected and rec.selected.label == "steady"
    assert "0.4 x relative throughput" in rec.rationale[1]
    flipped = Policy(balanced={"throughput": 0.9, "reliability": 0.05, "consistency": 0.05})
    chosen = recommend("balanced", [fast_sloppy, steady], flipped, RAM).selected
    assert chosen is not None and chosen.label == "fast_sloppy"


def test_balanced_skips_configs_without_consistency() -> None:
    rec = recommend("balanced", [ev("a", 50, cons=None), ev("b", 40, cons=0.8)], Policy(), RAM)
    assert rec.selected and rec.selected.label == "b"
    assert any(c.label == "a" and "consistency not measured" in c.detail for c in rec.considered)


def test_quality_prefers_consistency_over_speed() -> None:
    rec = recommend(
        "quality", [ev("fast", 100, cons=0.6), ev("careful", 20, cons=0.95)], Policy(), RAM
    )
    assert rec.selected and rec.selected.label == "careful"
    assert any("not a quality measure" in c for c in rec.caveats)


def test_low_memory_picks_smallest_peak() -> None:
    rec = recommend(
        "low_memory", [ev("big", 100, mem=6000), ev("small", 20, mem=1200)], Policy(), RAM
    )
    assert rec.selected and rec.selected.label == "small"


def test_overnight_requires_soak_else_provisional() -> None:
    no_soak = recommend("overnight", [ev("a", 50)], Policy(), RAM)
    assert no_soak.provisional and no_soak.selected and "provisional" in no_soak.rationale[-1]

    soaked = ev(
        "soaked",
        40,
        soak=SoakEvidence(duration_s=600, drift=0.95, failure_rate=0.0, valid_per_min=38),
    )
    drifting = ev(
        "drifting",
        90,
        soak=SoakEvidence(duration_s=600, drift=0.4, failure_rate=0.0, valid_per_min=30),
    )
    short = ev(
        "short", 80, soak=SoakEvidence(duration_s=30, drift=1.0, failure_rate=0.0, valid_per_min=80)
    )
    rec = recommend("overnight", [soaked, drifting, short], Policy(), RAM)
    assert not rec.provisional and rec.selected and rec.selected.label == "soaked"
    status = {c.label: c.status for c in rec.considered}
    assert status["drifting"] == "excluded" and status["short"] == "not_benchmarked"


def test_privacy_first_excludes_remote_runtimes() -> None:
    remote = ev("remote", 100, base_url="http://203.0.113.5:8080")
    rec = recommend("privacy_first", [remote, ev("local", 50)], Policy(), RAM)
    assert rec.selected and rec.selected.label == "local"
    assert any(c.label == "remote" and "not on this machine" in c.detail for c in rec.considered)


def test_mock_results_never_recommended_by_default() -> None:
    mock = ev("mock", 1000, runtime_kind="mock")
    assert recommend("fastest", [mock], Policy(), RAM).selected is None
    assert recommend("fastest", [mock], Policy(), RAM, include_mock=True).selected is not None


def test_parameter_parsing() -> None:
    assert parameter_billions("3.1B", "x") == 3.1
    assert parameter_billions(None, "mlx-community/Qwen2.5-3B-Instruct-4bit") == 3.0
    assert parameter_billions(None, "qwen2.5:1.5b") == 1.5
    assert parameter_billions(None, "model") is None
