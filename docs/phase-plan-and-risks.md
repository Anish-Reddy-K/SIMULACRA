# Phase plan, acceptance criteria, risks

Each phase: Plan → Build → Test → Verify → Fix → Document → **STOP for approval**. Acceptance criteria below are measurable gates; performance numbers are deliberately absent until Phase 4 baselines exist.

| # | Phase | Key acceptance criteria |
|---|---|---|
| 1 | Foundation | Fresh clone → `make dev`/`uv sync` + `npm ci` → API health + web page up; CI (ruff, mypy, pytest, tsc, vitest, license + dependency audit) green; Alembic up/down works; binds 127.0.0.1 only; host-header test |
| 2 | Design system/shell | Tokens pass contrast unit tests; all shell screens keyboard-navigable; axe 0 serious violations; Playwright screenshots at 3 widths × 2 themes reviewed |
| 3 | Inference adapters | Real generation on this Mac through ≥2 runtimes; discovery + health + schema-constrained output + telemetry; mock backend for CI; adapters degrade gracefully when a runtime is absent |
| 4 | Inference Lab | Gate in spec §4.13; benchmark reruns on same config agree within reported dispersion; invalid-output rate measured; recommendation traces to rows; memory guard prevents OOM by test; every figure real |
| 5 | Population factory | 100 and 1,000 personas: realized marginals within tolerance of spec (tests), zero duplicate IDs, diversity report, reproducible from seed, import/export round-trip |
| 6 | Durable execution | Kill -9 worker mid-run → resumes, **zero duplicate or lost trials** (asserted); pause/resume/cancel; SSE reconnect w/o gaps; DB contention test |
| 7 | First experiment | Wizard → 100 real local trials → report in browser (Playwright, screenshots); every report number reproducible by independent SQL check |
| 8 | A/B + pricing | Randomization balance test; treatment isolation test; stats verified against SciPy reference on fixtures |
| 9 | 10k scaling | 100/1k/10k measured (runtime, trials/min, tok/s, peak mem, failure/retry, DB size, recovery); overnight soak; publish only what happened |
| 10 | Analysis/reports | Claim-to-data audit: automated check that each report numeric claim matches recomputation; DuckDB decision made from measurement |
| 11 | Validation | Real-human-data evaluation pipeline; publish negative results |
| 12 | Advanced envs | Only features with demonstrated value |
| 13 | Release | Clean-machine install from README only; docs, security policy, license, CI release artifacts |

## Risks

| Risk | Likelihood/impact | Mitigation |
|---|---|---|
| **16 GB RAM / 23 GB free disk on target Mac** limits model size, parallel slots, and number of models benchmarkable | High / High | Disk and RAM guards in Lab; prefer ≤4–8B-class quantized models; benchmark one model at a time; document budget; delete-model guidance |
| 10k trials/night infeasible on a given model | Medium / High | Feasibility math shown up front (below); Lab recommends smaller model/shorter prompts; prefix-caching-friendly prompt layout |
| Runtime churn (Ollama MLX preview, vllm-mlx/metal young) | High / Medium | Capability probing, version recorded, adapters thin; unsupported combos fail soft |
| Python 3.14 system default breaks ML wheels | Medium / Medium | `uv` pins 3.12 (ADR-0001) |
| LLM outputs are homogeneous/agreeable (known: Pew, sycophancy) | High / High (scientific) | Diversity diagnostics, price-monotonicity and constraint invariants, prominent limitations, no accuracy claims |
| SQLite writer contention | Low / Medium | WAL, batched commits, tested |
| Scope creep (12 listed use cases) | High / High | MVP = product-concept → ad A/B → pricing only; others deferred |
| AGPL contamination from MiroFish | Low / High | Clean-room rule (ADR-0008) |
| Secondary-source facts here may be wrong | Medium / Low | Facts flagged "verify"; primary sources re-read in the phase that depends on them |

**Feasibility arithmetic (not a benchmark):** 10,000 trials in an 8-hour night requires ≥ ~21 valid trials/min (≈0.35/s) sustained. At an assumed ~600 tokens per trial that is ~6M tokens total. Whether this machine meets that is unknown until Phase 4.

## Decisions (resolved by owner)
1. License: Apache-2.0.
2. Static-export frontend served by FastAPI: approved.
3. DuckDB/Polars deferred to Phase 10 (owner delegated; kept as recommended).
4. Python 3.12 via uv, npm: approved.
5. Model disk budget: about 10 GB, at most two small models at a time (owner delegated).
6. Repo stays at this location; git initialized.
