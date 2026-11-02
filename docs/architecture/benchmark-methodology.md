# Inference Lab: Benchmark Methodology (Phase 0 proposal)

Nothing here has been measured yet. All thresholds are **placeholders to be set from Phase 4 baselines**.

## Stages
| Stage | Purpose | Cost | Output |
|---|---|---|---|
| 1 Compatibility | Load model, one tiny request, JSON-schema probe | seconds | pass/fail + reason |
| 2 Quick | Workloads A, B, E at concurrency 1 and 4, ~20 trials each | ~1–3 min/config | rough trials/min, valid rate |
| 3 Narrow | Drop configs failing floors or dominated on both speed and validity | instant | candidate list + reasons |
| 4 Detailed | B, C, D, F at concurrency sweep {1,2,4,8,…} until throughput plateaus or memory trips; ≥3 reps | 10–30 min/config | metrics with dispersion |
| 5 Reliability | G: sustained run (default 20–30 min; "overnight soak" optional) with drift/degradation tracking | long | stability curve |
| 6 Recommend | Policy engine (ADR-0007) | instant | per-goal picks + evidence |

Users can skip after Stage 1 and use a known-compatible default; skipped configs are labeled "not benchmarked."

## Workloads
A short classification · B persona decision (primary) · C long persona context · D batch (hundreds of independent trials) · E strict JSON schema conformity · F behavioral consistency · G sustained stability. Prompts, personas, and seeds are fixed, versioned files in `benchmarks/` with a content hash recorded in every result.

## Metrics
Prefill tok/s and decode tok/s measured separately (from runtime-reported timings where available, else client-side with the method recorded); TTFT; median/p95 latency; cold vs warm; **valid trials/min** (primary); memory (peak/sustained RSS + system pressure); timeouts, invalid-JSON, retries, server failures; CPU%. GPU% is not collected by default (needs root).

## Behavioral invariants (Workload F) — deterministic where possible
Hard-constraint personas (e.g. $100 budget, no credit, rent due) vs. a $600 purchase → **must not** "buy now"; tolerated outcomes defined per case. Also: price monotonicity (higher price must not raise purchase probability, tested statistically), paraphrase invariance (equivalent wording → same decision rate within tolerance), logical-equivalence pairs, persona-vs-instruction conflict, memory-fact recall, repeated-trial agreement. Scored as **invariant pass rates and stability**, never as "agreement with a preferred answer." Subjective items report variance only. These are *proxy checks*, not measures of human realism, and the UI says so.

## Fairness and recording
Per result: model identifier + digest/revision, quantization, runtime + version, runtime flags, context size, slots/concurrency, sampling params, prompt-template hash, benchmark seed, max output tokens, hardware profile, thermal/power state, timestamp. Compare only like-for-like workloads; flag unmatched quantizations.

## Evidence-quality label (shown on every result)
`screened` (Stage 1) · `quick` (n small, 1 rep) · `detailed` (≥3 reps, dispersion shown) · `soak` (sustained). Quick results carry a visible "indicative only" badge.

## Telemetry during real runs
Rolling throughput, failure rate, and memory pressure are stored locally to refine ETA and to suggest re-benchmarking on significant drift. Runtime config is **frozen per run**; any adaptive change is an explicit `run_event` and manifest entry.

## Open questions to resolve empirically in Phase 3/4
Does Ollama's MLX path activate on 16 GB? How does llama-server slot count trade vs. context on 16 GB? Does mlx-lm's server batch? Is vllm-mlx/vllm-metal installable without a curl-to-bash step we would refuse to automate?
