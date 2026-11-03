"""Statistical correctness: textbook values, independent recomputation, and null simulations."""

import math
import random
from collections import Counter

import numpy as np
import pytest
from scipy import stats as sps

from simulacra.analysis import stats
from simulacra.experiments.assign import assign_treatment


def test_newcombe_matches_published_example() -> None:
    # Newcombe (1998), Statistics in Medicine 17:873-890, example 1: 56/70 vs 48/80.
    lo, hi = stats.newcombe_diff_ci(56, 70, 48, 80)
    assert lo == pytest.approx(0.0524, abs=1e-3) and hi == pytest.approx(0.3339, abs=1e-3)
    lo, hi = stats.newcombe_diff_ci(0, 20, 0, 20)  # degenerate but finite
    assert lo < 0 < hi


def test_cohens_h_known_values() -> None:
    assert stats.cohens_h(0.5, 0.5) == 0
    expected = 2 * (math.asin(math.sqrt(0.6)) - math.asin(math.sqrt(0.4)))
    assert stats.cohens_h(0.6, 0.4) == pytest.approx(expected) == pytest.approx(0.4027, abs=1e-3)
    assert stats.cohens_h(0.1, 0.9) == pytest.approx(-stats.cohens_h(0.9, 0.1))


def test_holm_worked_example() -> None:
    # sorted: .005 .01 .03 .04  ->  x4 x3 x2 x1 = .02 .03 .06 .04 -> monotone .02 .03 .06 .06
    adj = stats.holm_adjust([0.01, 0.04, 0.03, 0.005])
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert stats.holm_adjust([0.5]) == [0.5]
    assert stats.holm_adjust([0.4, 0.9]) == pytest.approx([0.8, 0.9])
    assert max(stats.holm_adjust([0.2, 0.3, 0.9])) <= 1.0
    assert stats.holm_adjust([]) == []


def exact_fisher(a: int, b: int, c: int, d: int) -> float:
    """Independent two-sided Fisher exact test from the hypergeometric pmf."""
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def pmf(x: int) -> float:
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)

    p_obs = pmf(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p_obs * (1 + 1e-9)))


@pytest.mark.parametrize(
    "k1,n1,k2,n2", [(8, 20, 3, 20), (15, 40, 15, 40), (0, 10, 9, 10), (30, 100, 45, 100)]
)
def test_fisher_matches_independent_calculation_and_scipy(
    k1: int, n1: int, k2: int, n2: int
) -> None:
    ours = stats.fisher_p(k1, n1, k2, n2)
    assert ours == pytest.approx(exact_fisher(k1, n1 - k1, k2, n2 - k2), rel=1e-6)
    assert ours == pytest.approx(sps.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1])


def test_mcnemar_exact_matches_binomial_tail() -> None:
    b, c = 3, 10
    expected = min(
        1.0, 2 * sum(math.comb(b + c, k) for k in range(0, min(b, c) + 1)) / 2 ** (b + c)
    )
    assert stats.mcnemar_exact_p(b, c) == pytest.approx(expected)
    assert stats.mcnemar_exact_p(0, 0) == 1.0
    assert stats.mcnemar_exact_p(5, 5) == pytest.approx(1.0)


def test_welch_matches_manual_formula() -> None:
    a = [4, 5, 3, 4, 5, 4, 3, 5, 4, 4]
    b = [2, 3, 3, 2, 4, 3, 2, 3, 3, 2, 3, 2]
    na, nb = len(a), len(b)
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    t = (ma - mb) / math.sqrt(va / na + vb / nb)
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    p = 2 * sps.t.sf(abs(t), df)
    out = stats.welch(a, b)
    assert (
        out["t"] == pytest.approx(t)
        and out["p"] == pytest.approx(p)
        and out["diff"] == pytest.approx(ma - mb)
    )
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    assert out["d"] == pytest.approx((ma - mb) / pooled)
    assert stats.welch([1.0], [2.0, 3.0])["p"] is None
    assert stats.welch([3, 3, 3], [3, 3, 3])["p"] == 1.0  # zero variance, equal means


def test_paired_t_matches_scipy_and_handles_constant_differences() -> None:
    a, b = [4, 5, 3, 4, 5, 4], [3, 4, 3, 3, 4, 4]
    out = stats.paired_t(a, b)
    assert out["p"] == pytest.approx(float(sps.ttest_rel(a, b).pvalue))
    assert stats.paired_t([2, 3], [1, 2])["p"] == 0.0  # constant non-zero shift


def test_chi_square_matches_manual_calculation() -> None:
    table = [[20, 10], [10, 20], [15, 15]]
    total = sum(map(sum, table))
    rows, cols = [sum(r) for r in table], [sum(c) for c in zip(*table, strict=True)]
    chi = sum(
        (table[i][j] - rows[i] * cols[j] / total) ** 2 / (rows[i] * cols[j] / total)
        for i in range(3)
        for j in range(2)
    )
    assert stats.chi_square_p(table) == pytest.approx(float(sps.chi2.sf(chi, 2)))
    assert stats.chi_square_p([[5, 5]]) == 1.0
    assert stats.chi_square_p([[10, 0], [10, 0]]) == 1.0  # a constant column carries no information


def test_null_ab_tests_do_not_over_reject() -> None:
    """A/A tests: two arms from the same distribution. False positives must be near or below 5%."""
    rng = np.random.default_rng(0)
    sims, hits, hits_holm = 2000, 0, 0
    for _ in range(sims):
        n = 60
        k1, k2, k3 = (int(rng.binomial(n, 0.3)) for _ in range(3))
        p12, p13 = stats.fisher_p(k1, n, k2, n), stats.fisher_p(k1, n, k3, n)
        hits += p12 < 0.05
        hits_holm += min(stats.holm_adjust([p12, p13])) < 0.05
    assert hits / sims < 0.06  # Fisher is conservative
    assert hits_holm / sims < 0.06  # family-wise control over two comparisons


def test_power_exists_for_a_real_difference() -> None:
    rng = np.random.default_rng(1)
    detected = sum(
        stats.fisher_p(int(rng.binomial(200, 0.40)), 200, int(rng.binomial(200, 0.25)), 200) < 0.05
        for _ in range(300)
    )
    assert detected / 300 > 0.8


def test_random_assignment_is_balanced_in_practice() -> None:
    """Balance checks should flag imbalance about as often as chance dictates under real randomization."""
    rnd = random.Random(3)
    regions = ["n", "s", "e", "w"]
    personas = [{"region": rnd.choice(regions), "age": rnd.randint(18, 80)} for _ in range(600)]
    flagged = 0
    runs = 150
    for seed in range(runs):
        arms = [assign_treatment(seed, f"P{i}", 3) for i in range(600)]
        table = [
            [
                sum(1 for p, a in zip(personas, arms, strict=True) if a == arm and p["region"] == r)
                for r in regions
            ]
            for arm in range(3)
        ]
        flagged += stats.chi_square_p(table) < 0.05
    assert flagged / runs < 0.12  # nominal 5%, allow sampling noise
    sizes = Counter(assign_treatment(1, f"P{i}", 3) for i in range(3000))
    assert max(sizes.values()) - min(sizes.values()) < 150
