"""Statistical primitives. Pure functions, verified against textbook examples and SciPy in tests.

Everything here describes sampling variation of a simulation. None of it quantifies
uncertainty about real-world behavior.
"""

import math
import warnings
from collections.abc import Sequence

from scipy import stats

from simulacra.analysis.concept import wilson


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int, z: float = 1.96) -> tuple[float, float]:
    """Newcombe (1998) hybrid score interval (method 10) for p1 - p2."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lower, upper)


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for a difference between two proportions."""
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def holm_adjust(pvalues: Sequence[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def fisher_p(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided Fisher exact test on [[k1, n1-k1], [k2, n2-k2]]."""
    return float(stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1])


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact McNemar test from the two discordant counts (paired designs)."""
    if b + c == 0:
        return 1.0
    return float(stats.binomtest(min(b, c), b + c, 0.5).pvalue)


def welch(a: Sequence[float], b: Sequence[float]) -> dict[str, float | None]:
    """Welch's t-test with Cohen's d (pooled SD) for a - b."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"diff": None, "t": None, "p": None, "d": None}
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    if va == 0 and vb == 0:
        return {"diff": ma - mb, "t": None, "p": 1.0 if ma == mb else 0.0, "d": None}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # near-constant ratings are legitimate
        res = stats.ttest_ind(a, b, equal_var=False)
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    return {
        "diff": ma - mb,
        "t": float(res.statistic),
        "p": float(res.pvalue),
        "d": (ma - mb) / pooled if pooled > 0 else None,
    }


def paired_t(a: Sequence[float], b: Sequence[float]) -> dict[str, float | None]:
    if len(a) < 2:
        return {"diff": None, "t": None, "p": None}
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    if max(diffs) == min(diffs):
        return {"diff": diffs[0], "t": None, "p": 1.0 if diffs[0] == 0 else 0.0}
    res = stats.ttest_rel(a, b)
    return {"diff": sum(diffs) / len(diffs), "t": float(res.statistic), "p": float(res.pvalue)}


def chi_square_p(table: list[list[int]]) -> float:
    """Chi-square test of independence for a contingency table (balance checks)."""
    rows = [r for r in table if sum(r) > 0]
    cols = [j for j in range(len(rows[0])) if sum(r[j] for r in rows) > 0] if rows else []
    reduced = [[r[j] for j in cols] for r in rows]
    if len(reduced) < 2 or len(cols) < 2:
        return 1.0
    return float(stats.chi2_contingency(reduced)[1])
