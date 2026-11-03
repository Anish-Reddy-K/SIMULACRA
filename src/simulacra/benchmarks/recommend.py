"""Transparent recommendation engine (ADR-0007). Pure functions, no LLM, no I/O.

Only configurations with measured evidence are ever ranked. Everything else is listed as
excluded or "not benchmarked" with the reason.
"""

import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from simulacra.benchmarks.invariants import Diagnostic, consistency_score
from simulacra.benchmarks.policy import Policy
from simulacra.persistence.models import BenchmarkResult

Goal = Literal["fastest", "balanced", "quality", "overnight", "low_memory", "privacy_first"]
GOALS: tuple[Goal, ...] = (
    "fastest",
    "balanced",
    "quality",
    "overnight",
    "low_memory",
    "privacy_first",
)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class SoakEvidence(BaseModel):
    duration_s: float
    drift: float | None
    failure_rate: float
    valid_per_min: float


class ConfigEvidence(BaseModel):
    """Everything measured about one (runtime, model, structured-mode) configuration."""

    key: str
    label: str
    runtime_kind: str
    runtime_version: str | None
    base_url: str
    model: str
    quantization: str | None
    parameter_b: float | None
    structured_mode: str
    evidence: str  # best evidence level reached: screened | quick | detailed | soak
    compat_ok: bool
    compat_error: str | None = None
    json_schema_works: bool | None = None
    valid_per_min: float | None = None
    best_concurrency: int | None = None
    decode_tokens_per_s: float | None = None
    decode_tps_method: str | None = None
    valid_rate: float | None = None
    failure_rate: float | None = None
    peak_rss_mb: float | None = None
    min_available_mb: float | None = None
    swap_growth_mb: float | None = None
    consistency: float | None = None
    soak: SoakEvidence | None = None
    result_ids: list[int] = []

    @property
    def benchmarked(self) -> bool:
        return self.valid_per_min is not None


class Consideration(BaseModel):
    label: str
    status: Literal["selected", "ranked", "excluded", "not_benchmarked"]
    detail: str


class Recommendation(BaseModel):
    goal: Goal
    title: str
    selected: ConfigEvidence | None
    provisional: bool = False
    rationale: list[str]
    considered: list[Consideration]
    caveats: list[str]
    when_different: str
    policy_version: str


_EVIDENCE_ORDER = {"screened": 0, "quick": 1, "detailed": 2, "soak": 3}
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")


def parameter_billions(parameter_size: str | None, model: str) -> float | None:
    for text in (parameter_size or "", model):
        if m := _SIZE.search(text.replace("-", " ").replace(":", " ")):
            return float(m.group(1))
    return None


def _config_key(r: BenchmarkResult) -> str:
    return f"{r.runtime_kind}|{r.base_url}|{r.model}|{r.structured_mode}"


def build_evidence(rows: list[BenchmarkResult]) -> list[ConfigEvidence]:
    """Collapse stored results into one evidence record per configuration.

    For each configuration the most recent run that produced a given stage is used, so a
    re-benchmark replaces older numbers instead of mixing them.
    """
    groups: dict[str, list[BenchmarkResult]] = {}
    for r in rows:
        groups.setdefault(_config_key(r), []).append(r)
    out: list[ConfigEvidence] = []
    for key, items in groups.items():
        latest_run: dict[str, int] = {}
        for r in items:  # keep latest run per stage
            latest_run[r.stage] = max(latest_run.get(r.stage, r.run_id), r.run_id)
        sel = [r for r in items if r.run_id == latest_run[r.stage]]
        first = sel[0]
        compat = next(
            (r.compat_json for r in sel if r.workload == "compat" and r.compat_json), None
        )
        ev = ConfigEvidence(
            key=key,
            label=f"{first.runtime_kind} / {first.model}"
            + (" (prompted JSON)" if first.structured_mode == "prompted" else ""),
            runtime_kind=first.runtime_kind,
            runtime_version=first.runtime_version,
            base_url=first.base_url,
            model=first.model,
            quantization=first.quantization,
            parameter_b=parameter_billions(first.parameter_size, first.model),
            structured_mode=first.structured_mode,
            evidence=max((r.evidence for r in sel), key=lambda e: _EVIDENCE_ORDER[e]),
            compat_ok=bool(compat and compat.get("ok")),
            compat_error=compat.get("error") if compat else None,
            json_schema_works=compat.get("structured_json_schema_works") if compat else None,
            result_ids=[r.id for r in sel],
        )
        # Headline numbers come from the best evidence stage available (detailed > quick).
        for stage in ("detailed", "quick"):
            b_rows = [r for r in sel if r.stage == stage and r.workload == "B" and r.metrics_json]
            if b_rows:
                best = max(
                    b_rows, key=lambda r: (r.metrics_json or {}).get("valid_trials_per_min", 0)
                )
                m: dict[str, Any] = best.metrics_json or {}
                ev.valid_per_min = m["valid_trials_per_min"]
                ev.best_concurrency = best.concurrency
                ev.decode_tokens_per_s = m.get("decode_tokens_per_s_median")
                ev.decode_tps_method = m.get("decode_tps_method")
                break
        measured = [r.metrics_json for r in sel if r.metrics_json and r.workload != "G"]
        if measured:
            ev.valid_rate = sum(m["valid_rate"] * m["n"] for m in measured) / sum(
                m["n"] for m in measured
            )
            ev.failure_rate = sum(m["failure_rate"] * m["n"] for m in measured) / sum(
                m["n"] for m in measured
            )
            peaks = [m["peak_rss_mb"] for m in measured if m.get("peak_rss_mb") is not None]
            ev.peak_rss_mb = max(peaks) if peaks else None
            ev.min_available_mb = (
                min(
                    m["min_available_mb"] for m in measured if m.get("min_available_mb") is not None
                )
                if any(m.get("min_available_mb") is not None for m in measured)
                else None
            )
            ev.swap_growth_mb = max((m.get("swap_growth_mb") or 0.0) for m in measured)
        f_rows = [r for r in sel if r.workload == "F" and r.diagnostics_json]
        if f_rows:
            ev.consistency = consistency_score(
                [Diagnostic(**d) for d in f_rows[-1].diagnostics_json]
            )
        g = next((r for r in sel if r.workload == "G" and r.metrics_json), None)
        if g and g.metrics_json:
            ev.soak = SoakEvidence(
                duration_s=g.extras_json.get("duration_s", g.metrics_json["wall_s"]),
                drift=g.extras_json.get("throughput_drift"),
                failure_rate=g.metrics_json["failure_rate"],
                valid_per_min=g.metrics_json["valid_trials_per_min"],
            )
        out.append(ev)
    return out


def _exclusion(ev: ConfigEvidence, policy: Policy, ram_total_mb: float) -> str | None:
    if not ev.compat_ok:
        return f"failed compatibility screening ({ev.compat_error or 'no response'})"
    if not ev.benchmarked:
        return None  # handled separately as not_benchmarked
    if ev.peak_rss_mb is not None and ev.peak_rss_mb > policy.safe_memory_fraction * ram_total_mb:
        return (
            f"peak memory {ev.peak_rss_mb:.0f} MB exceeds the safe limit "
            f"({policy.safe_memory_fraction:.0%} of {ram_total_mb:.0f} MB)"
        )
    if ev.min_available_mb is not None and ev.min_available_mb < policy.min_available_mb:
        return f"system available memory fell to {ev.min_available_mb:.0f} MB (floor {policy.min_available_mb:.0f} MB)"
    if ev.swap_growth_mb is not None and ev.swap_growth_mb > policy.max_swap_growth_mb:
        return f"swap grew by {ev.swap_growth_mb:.0f} MB during the benchmark"
    if ev.valid_rate is not None and ev.valid_rate < policy.min_valid_rate:
        return f"valid structured-output rate {ev.valid_rate:.0%} is below the {policy.min_valid_rate:.0%} floor"
    if ev.failure_rate is not None and ev.failure_rate > policy.max_failure_rate:
        return f"request failure rate {ev.failure_rate:.0%} is above the {policy.max_failure_rate:.0%} ceiling"
    return None


def _fmt(ev: ConfigEvidence) -> str:
    parts = [f"{ev.valid_per_min:.1f} valid trials/min at concurrency {ev.best_concurrency}"]
    if ev.decode_tokens_per_s:
        parts.append(f"{ev.decode_tokens_per_s:.0f} tokens/s decode ({ev.decode_tps_method})")
    if ev.peak_rss_mb:
        parts.append(f"peak server memory {ev.peak_rss_mb:.0f} MB")
    if ev.valid_rate is not None:
        parts.append(f"{ev.valid_rate:.0%} valid output")
    if ev.consistency is not None:
        parts.append(f"{ev.consistency:.0%} on consistency invariants")
    return ", ".join(parts)


TITLES: dict[Goal, str] = {
    "fastest": "Fastest",
    "balanced": "Best balanced",
    "quality": "Highest local quality",
    "overnight": "Overnight large-scale",
    "low_memory": "Low memory",
    "privacy_first": "Privacy-first",
}
WHEN: dict[Goal, str] = {
    "fastest": "Choose a more balanced option when output validity or consistency matters more than speed.",
    "balanced": "Choose the fastest option for quick exploration, or the quality option when subtle constraint-following matters.",
    "quality": "Choose a faster option when you need thousands of trials and can accept a weaker model; consistency invariants are proxies, not human realism.",
    "overnight": "A short soak is not an overnight run. Re-run a longer soak before trusting a multi-hour job.",
    "low_memory": "Choose a larger model when memory is not the constraint; small models can score lower on consistency.",
    "privacy_first": "All runtimes Simulacra supports run on this machine. Choose by goal when every candidate is local.",
}


def recommend(
    goal: Goal,
    evidence: list[ConfigEvidence],
    policy: Policy,
    ram_total_mb: float,
    include_mock: bool = False,
) -> Recommendation:
    caveats = [
        "Based on proxy metrics from synthetic workloads. These do not measure accuracy against real people."
    ]
    considered: list[Consideration] = []
    pool: list[ConfigEvidence] = []
    for ev in evidence:
        if ev.runtime_kind == "mock" and not include_mock:
            continue
        if not ev.benchmarked and ev.compat_ok:
            considered.append(
                Consideration(
                    label=ev.label,
                    status="not_benchmarked",
                    detail="compatible, but no benchmark measurements yet",
                )
            )
            continue
        reason = _exclusion(ev, policy, ram_total_mb)
        if (
            reason is None
            and goal == "privacy_first"
            and urlparse(ev.base_url).hostname not in LOOPBACK
        ):
            reason = "runtime is not on this machine"
        if reason is None and ev.compat_ok and ev.benchmarked and ev.evidence == "quick":
            caveats.append(f"{ev.label}: quick benchmark only, indicative.")
        if reason:
            considered.append(Consideration(label=ev.label, status="excluded", detail=reason))
        else:
            pool.append(ev)

    def finish(
        ranked: list[ConfigEvidence],
        why: list[str],
        notes: list[str] | None = None,
        provisional: bool = False,
    ) -> Recommendation:
        for i, ev in enumerate(ranked):
            considered.append(
                Consideration(
                    label=ev.label, status="selected" if i == 0 else "ranked", detail=_fmt(ev)
                )
            )
        selected = ranked[0] if ranked else None
        rationale = ([f"Selected {selected.label}: {_fmt(selected)}."] if selected else []) + why
        if not selected:
            rationale = why or ["No configuration has the measurements this goal needs."]
        return Recommendation(
            goal=goal,
            title=TITLES[goal],
            selected=selected,
            provisional=provisional,
            rationale=rationale,
            considered=considered,
            caveats=caveats + (notes or []),
            when_different=WHEN[goal],
            policy_version=policy.version,
        )

    if not pool:
        return finish(
            [], ["Run a benchmark first. Nothing has been measured yet, so nothing is recommended."]
        )

    if goal == "fastest":
        ranked = sorted(pool, key=lambda e: -(e.valid_per_min or 0))
        return finish(
            ranked,
            ["Ranked by valid structured trials per minute at its best measured concurrency."],
        )
    if goal in ("balanced", "privacy_first"):
        scored = [e for e in pool if e.consistency is not None]
        for e in pool:
            if e.consistency is None:
                considered.append(
                    Consideration(
                        label=e.label,
                        status="excluded",
                        detail="consistency not measured, so it cannot be scored",
                    )
                )
        if not scored:
            return finish([], ["Balanced scoring needs consistency results (workload F)."])
        best = max(e.valid_per_min or 0 for e in scored)
        w = policy.balanced

        def score(e: ConfigEvidence) -> float:
            return (
                w.throughput * (e.valid_per_min or 0) / best
                + w.reliability * (e.valid_rate or 0)
                + w.consistency * (e.consistency or 0)
            )

        ranked = sorted(scored, key=lambda e: -score(e))
        why = [
            f"Score = {w.throughput} x relative throughput + {w.reliability} x valid-output rate + "
            f"{w.consistency} x consistency. Scores: "
            + "; ".join(f"{e.label} {score(e):.2f}" for e in ranked)
            + "."
        ]
        if goal == "privacy_first":
            why.append("Only runtimes on this machine were considered; nothing is sent elsewhere.")
        return finish(ranked, why)
    if goal == "quality":
        scored = [e for e in pool if e.consistency is not None]
        if not scored:
            return finish([], ["Quality ranking needs consistency results (workload F)."])
        ranked = sorted(
            scored,
            key=lambda e: (
                -(e.consistency or 0),
                -(e.valid_rate or 0),
                -(e.parameter_b or 0),
                -(e.valid_per_min or 0),
            ),
        )
        return finish(
            ranked,
            [
                "Ranked by consistency-invariant pass rate, then valid-output rate, then model size "
                "(a rough capacity proxy only), then throughput."
            ],
            ["Model size is not a quality measure; only the invariant results are evidence."],
        )
    if goal == "low_memory":
        measurable = [e for e in pool if e.peak_rss_mb is not None]
        if not measurable:
            return finish([], ["No memory measurements are available for any candidate."])
        ranked = sorted(measurable, key=lambda e: e.peak_rss_mb or 0)
        return finish(
            ranked,
            ["Ranked by lowest peak server-process memory during the benchmark."],
            [
                "RSS can under-report GPU memory on Apple Silicon; system available memory was also checked."
            ],
        )
    # overnight
    soaked = [e for e in pool if e.soak and e.soak.duration_s >= policy.soak_min_seconds]
    stable = [
        e
        for e in soaked
        if e.soak
        and e.soak.failure_rate <= policy.max_failure_rate
        and (e.soak.drift is None or e.soak.drift >= policy.soak_min_drift)
    ]
    for e in soaked:
        if e not in stable:
            considered.append(
                Consideration(
                    label=e.label,
                    status="excluded",
                    detail="soak run showed throughput drift or failures",
                )
            )
    for e in pool:
        if e not in soaked:
            considered.append(
                Consideration(
                    label=e.label,
                    status="not_benchmarked",
                    detail=f"no soak run of at least {policy.soak_min_seconds:.0f}s",
                )
            )
    if stable:
        ranked = sorted(stable, key=lambda e: -(e.soak.valid_per_min if e.soak else 0))
        return finish(
            ranked,
            [
                "Only configurations with a completed soak run, low failures and stable throughput qualify."
            ],
        )
    fallback = sorted(pool, key=lambda e: (e.failure_rate or 0, -(e.valid_per_min or 0)))
    return finish(
        fallback,
        [
            "No configuration has a qualifying soak run yet, so this pick is provisional: "
            "lowest failure rate, then throughput."
        ],
        provisional=True,
        notes=["Run the soak stage before starting a multi-hour experiment."],
    )
