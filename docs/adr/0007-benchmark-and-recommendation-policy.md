# ADR-0007: Benchmark and recommendation policy

**Status:** Proposed (Phase 0). Full method in `docs/architecture/benchmark-methodology.md`.

## Decision
A **deterministic, documented policy engine** — no LLM in the ranking path.

1. Filter: incompatible → exceeds safe-memory budget → fails reliability floor (e.g. valid-output rate, timeouts). Each exclusion is recorded with its reason.
2. Per goal (fastest, balanced, local quality, overnight, low-memory, privacy-first) apply a **goal-specific rule** over measured vectors: lexicographic constraints + a weighted sum **only within the surviving set**, weights in a visible, editable config file.
3. Present the **Pareto front** (throughput × consistency × memory) alongside the pick, so users see trade-offs.
4. Every recommendation cites the benchmark rows it used; unbenchmarked configs are shown as "not measured" and never ranked.
5. **No single universal score.** Speed, structured reliability, behavioral invariants, and (later) empirical validity stay separate columns.

## Primary metric
**Valid completed trials per minute at the best stable concurrency**, on the representative workload (persona decision with structured JSON), not raw tokens/s.

## Fairness controls
Identical prompts/seeds/max-output-tokens across configs; matched or explicitly labeled quantizations; throughput normalized by output length; warm vs cold reported separately; thermal state and power source recorded; ≥3 repetitions for the detailed stage with dispersion reported.

## macOS measurement limits (no unnecessary permissions)
- Memory: per-process RSS/footprint via `psutil`, system pressure via `vm_stat`/`memory_pressure`. Works unprivileged.
- GPU utilization: `powermetrics` requires root → **not collected by default**; shown as "not measured" (optional, user-initiated sudo later).
- Hardware info stays local; no transmission without explicit opt-in.

## Safety
Model downloads are explicit user actions with size and free-disk shown first. **This machine has ~23 GB free of 228 GB (89% used)** — the Lab must enforce a disk-headroom check before any pull.

## Rejected
LLM-judged ranking; one blended score; auto-switching models mid-experiment.
