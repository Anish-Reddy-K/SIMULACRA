"""Tests use a tiny SYNTHETIC fixture to verify the metrics. It is not real human data."""

import math

import pytest

from simulacra.evaluation import real_data as rd


def csv_bytes(rows: list[tuple[str, str, str]]) -> bytes:
    lines = ["region,age_band,would_buy"] + [",".join(r) for r in rows]
    return "\n".join(lines).encode()


def test_parse_maps_positive_values_and_skips_missing() -> None:
    raw = csv_bytes(
        [
            ("west", "18-29", "yes"),
            ("west", "18-29", "No"),
            ("south", "30-44", ""),
            ("south", "30-44", "YES"),
        ]
    )
    rows = rd.parse_real_csv(raw, "would_buy", {"yes", "1", "true"})
    assert [r["would_buy"] for r in rows] == ["1", "0", "1"]  # the blank outcome is excluded


def test_parse_rejects_bad_files() -> None:
    with pytest.raises(rd.EvaluationError, match="needs an"):
        rd.parse_real_csv(b"a,b\n1,2\n", "would_buy", {"yes"})
    with pytest.raises(rd.EvaluationError, match="UTF-8"):
        rd.parse_real_csv(b"\xff\xfe\x00", "would_buy", {"yes"})
    with pytest.raises(rd.EvaluationError, match="no usable rows"):
        rd.parse_real_csv(b"would_buy\n\n \n", "would_buy", {"yes"})
    with pytest.raises(rd.EvaluationError, match="50 MB"):
        rd.parse_real_csv(b"x" * (50 * 2**20 + 1), "would_buy", {"yes"})


def test_segment_join_uses_only_comparable_segments() -> None:
    rows = [{"region": "west", "would_buy": "1"}] * 20 + [{"region": "west", "would_buy": "0"}] * 20
    rows += [{"region": "south", "would_buy": "1"}] * 5  # too small: excluded
    rows += [{"region": "east", "would_buy": "0"}] * 30  # no simulated counterpart: excluded
    sim = [
        {"attribute": "region", "group": "west", "n": 50, "value": 0.7},
        {"attribute": "region", "group": "south", "n": 50, "value": 0.1},
    ]
    obs = rd.segment_observations(rows, "would_buy", sim, ["region"])
    assert [(o.segment, o.real, o.sim, o.n_real) for o in obs] == [("region=west", 0.5, 0.7, 40)]


def test_metrics_match_hand_calculation() -> None:
    obs = [
        rd.Observation(f"s{i}", 100, real, 100, sim)
        for i, (real, sim) in enumerate([(0.10, 0.30), (0.20, 0.40), (0.30, 0.50), (0.40, 0.60)])
    ]
    out = rd.evaluate(obs, overall_real=0.25, overall_sim=0.45)
    assert (
        out["mae"] == pytest.approx(0.2)
        and out["rmse"] == pytest.approx(0.2)
        and out["bias"] == pytest.approx(0.2)
    )
    assert out["pearson"] == pytest.approx(1.0) and out["spearman"] == pytest.approx(1.0)
    assert out["calibration"]["slope"] == pytest.approx(1.0) and out["calibration"][
        "intercept"
    ] == pytest.approx(-0.2)
    assert out["variation_ratio"] == pytest.approx(1.0) and out["overall"][
        "error"
    ] == pytest.approx(0.2)


def test_detects_compressed_variation_and_overagreement() -> None:
    real = [0.05, 0.20, 0.35, 0.50, 0.65]
    sim = [0.40 + 0.01 * i for i in range(5)]  # nearly flat and too high
    out = rd.evaluate(
        [
            rd.Observation(f"s{i}", 80, r, 80, s)
            for i, (r, s) in enumerate(zip(real, sim, strict=True))
        ],
        0.35,
        0.42,
    )
    assert out["variation_ratio"] < 0.1 and out["bias"] > 0 and out["calibration"]["slope"] > 5
    assert out["worst_segments"][0]["segment"] in ("s0", "s4")
    assert any("compressed variation" in line for line in out["interpretation"])


def test_evaluate_needs_enough_segments_and_handles_constants() -> None:
    with pytest.raises(rd.EvaluationError):
        rd.evaluate([rd.Observation("a", 50, 0.1, 50, 0.2)], 0.1, 0.2)
    flat = [rd.Observation(f"s{i}", 50, 0.3, 50, 0.3 + 0.1 * i) for i in range(4)]
    out = rd.evaluate(flat, 0.3, 0.45)
    assert out["pearson"] is None and out["variation_ratio"] is None  # no variance in the real data


def test_distribution_distances() -> None:
    same = rd.compare_distributions([0.5, 0.5], [0.5, 0.5])
    assert same["total_variation"] == 0 and same["jensen_shannon"] == pytest.approx(0)
    far = rd.compare_distributions([1.0, 0.0], [0.0, 1.0])
    assert far["total_variation"] == 1 and far["jensen_shannon"] == pytest.approx(1.0)
    half = rd.compare_distributions([0.75, 0.25], [0.25, 0.75])
    assert half["total_variation"] == pytest.approx(0.5) and 0 < half["jensen_shannon"] < 1
    assert math.isfinite(half["jensen_shannon"])
    with pytest.raises(rd.EvaluationError):
        rd.compare_distributions([1.0], [0.5, 0.5])
