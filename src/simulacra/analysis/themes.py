"""Lightweight, deterministic qualitative analysis of the free-text reasons.

Structured reason codes come first (they are exact). This module adds two cheap, auditable
views of the free text: distinctive terms per reason code (weighted log-odds with an
informative Dirichlet prior, Monroe et al. 2008) and greedy clusters of near-duplicate
reasons. No embeddings and no model calls; every theme links back to its source trials.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "too",
        "was",
        "we",
        "were",
        "what",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
        "not",
        "no",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "just",
        "really",
        "very",
        "more",
        "most",
        "much",
        "about",
        "also",
        "any",
        "some",
        "such",
        "only",
        "own",
        "same",
        "been",
        "being",
        "am",
        "im",
        "ive",
        "id",
        "dont",
        "wont",
        "cant",
        "it's",
        "i'm",
        "i've",
    ]
)
_TOKEN = re.compile(r"[a-z][a-z'-]{1,}")
MIN_TERM_COUNT = 3
CLUSTER_THRESHOLD = 0.5
MAX_CLUSTERS = 12


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


@dataclass
class Cluster:
    size: int
    exemplar_trial_id: int
    exemplar_text: str
    terms: list[str]
    trial_ids: list[int] = field(default_factory=list)


def distinctive_terms(
    groups: dict[str, list[str]], top: int = 6
) -> dict[str, list[dict[str, Any]]]:
    """For each group, the terms most over-represented against all other groups (z-scored)."""
    counts = {
        g: Counter(t for text in texts for t in set(tokens(text))) for g, texts in groups.items()
    }
    vocab = {t for c in counts.values() for t in c}
    if not vocab:
        return {g: [] for g in groups}
    alpha = 0.5
    alpha0 = alpha * len(vocab)
    total = {g: sum(c.values()) for g, c in counts.items()}
    out: dict[str, list[dict[str, Any]]] = {}
    for g, c in counts.items():
        rest: Counter[str] = Counter()
        for h, ch in counts.items():
            if h != g:
                rest.update(ch)
        n_g, n_r = total[g], sum(rest.values())
        scored: list[dict[str, Any]] = []
        for term, y_g in c.items():
            if y_g < MIN_TERM_COUNT:
                continue
            y_r = rest.get(term, 0)
            delta = math.log((y_g + alpha) / (n_g + alpha0 - y_g - alpha)) - math.log(
                (y_r + alpha) / (n_r + alpha0 - y_r - alpha)
            )
            z = delta / math.sqrt(1 / (y_g + alpha) + 1 / (y_r + alpha))
            if z > 0:
                scored.append({"term": term, "z": z, "count": y_g})
        scored.sort(key=lambda d: (-d["z"], d["term"]))
        out[g] = scored[:top]
    return out


def cluster_reasons(
    items: list[tuple[int, str]], threshold: float = CLUSTER_THRESHOLD
) -> list[Cluster]:
    """Greedy leader clustering on token-set Jaccard similarity. Deterministic given the order."""
    leaders: list[tuple[set[str], Cluster]] = []
    for trial_id, text in items:
        toks = set(tokens(text))
        if not toks:
            continue
        best: tuple[float, Cluster | None] = (0.0, None)
        for lead_toks, cluster in leaders:
            sim = len(toks & lead_toks) / len(toks | lead_toks)
            if sim > best[0]:
                best = (sim, cluster)
        if best[1] is not None and best[0] >= threshold:
            best[1].size += 1
            best[1].trial_ids.append(trial_id)
        else:
            leaders.append((toks, Cluster(1, trial_id, text, [], [trial_id])))
    clusters = sorted((c for _, c in leaders), key=lambda c: (-c.size, c.exemplar_trial_id))
    for lead_toks, c in [(t, c) for t, c in leaders]:
        c.terms = sorted(lead_toks)[:6]
    return clusters[:MAX_CLUSTERS]
