# Simulacra Architecture (Phase 0 proposal)

## 1. System diagram

```text
 Browser (static Next.js export)
     │  REST + SSE (127.0.0.1, token on mutations)
     ▼
 ┌─────────────── simulacra up (supervisor) ───────────────┐
 │  API process (FastAPI)            Worker process        │
 │  ├ routers: hardware, lab,        ├ claim batch (lease) │
 │  │  populations, experiments,     ├ build prompts       │
 │  │  runs, reports, settings       ├ InferenceRouter ────┼──► Ollama :11434
 │  ├ SSE from run_events            ├ validate + commit   │──► llama-server :8080
 │  └ serves static UI               └ heartbeat, events   │──► mlx-lm / vllm-mlx :8000
 └───────────────┬───────────────────────────┬─────────────┘
                 └────────► SQLite (WAL) ◄───┘
                   (jobs, trials, events, populations, benchmarks, reports)
```
Runtimes are **user-managed external processes**. Simulacra discovers, probes, and (only on explicit user action) starts them or pulls models. It never installs or switches silently.

## 2. Component responsibilities

| Module | Owns | Must not |
|---|---|---|
| `persistence` | engine, migrations, repositories, queue primitives | contain business rules |
| `inference` | backend protocol, Ollama + OpenAI-compat adapters, discovery, capability probes, retry/timeout, telemetry | know about personas |
| `benchmarks` | hardware probe, workloads A–G, invariant suites, runner, recommender policy | write experiment data |
| `personas` / `populations` | specs, copula sampler, enrichment, diagnostics, versioning, import/export | call inference directly (uses `inference` interface) |
| `experiments` | experiment/treatment models, assignment, outcome schemas, prompt builders | do stats |
| `simulation` | trial planner, batch executor, checkpointing, run state machine | HTTP concerns |
| `analysis` | deterministic stats, segment cuts, reason-code aggregation | call an LLM for numbers |
| `reporting` | report assembly, quote→trial linking, HTML/MD/JSON/CSV exports | invent claims not in computed data |
| `api` | HTTP/SSE schemas, auth token, host check | long-running work |
| `worker` | process loop, lease/heartbeat, signal handling | UI logic |

## 3. Run state machine
`created → queued → preparing → running ⇄ pausing → paused`; `running → cancelling → cancelled`; terminal: `completed | completed_with_errors | failed`. Transitions are validated in one function and each emits a `run_event`. Pause = stop claiming new batches, let in-flight batches finish (graceful); cancel = additionally abandon unstarted batches. A crashed worker's expired leases return batches to the queue; unique-constraint commits make replays safe.

## 4. Data model (initial; Alembic-managed)

- `hardware_profiles(id, captured_at, chip, arch, ram_total, os, disk_free, json)`
- `runtimes(id, kind, base_url, version, capabilities_json, last_seen)`
- `models(id, runtime_id, name, digest, quantization, size_bytes, license, params_json)`
- `benchmark_runs(id, hardware_id, stage, status, seed, config_json, started_at, finished_at)`
- `benchmark_results(id, run_id, runtime_id, model_id, workload, concurrency, metrics_json, samples_blob_ref, evidence_quality)`
- `recommendations(id, run_id, goal, runtime_id, model_id, rationale_json, policy_version)`
- `populations(id, name, current_version)`; `population_versions(id, population_id, spec_json, seed, diagnostics_json, created_at)`
- `personas(id, population_version_id, synthetic_id, attributes_json, bio, generation_meta_json)`
- `experiments(id, name, research_question, hypothesis, type, population_version_id, scenario_json, outcome_schema_json, config_json)`
- `treatments(id, experiment_id, label, params_json)`
- `runs(id, experiment_id, state, seed, manifest_json, created_at, ...)` — manifest is the frozen reproducibility record
- `jobs(id, run_id, batch_idx, state, lease_owner, lease_expires, attempts, payload_json)`
- `trials(id, run_id, persona_id, treatment_id, repeat_idx, prompt_text, raw_output, parsed_json, valid, error, tokens_in, tokens_out, latency_ms, created_at, UNIQUE(run_id, persona_id, treatment_id, repeat_idx))`
- `run_events(id, run_id, ts, kind, message, data_json)` — append-only; SSE source (`Last-Event-ID` = `id`)
- `reports(id, run_id, version, computed_json, rendered_html)`
- `settings(key, value)`

## 5. API contracts (v1, abbreviated)

```
GET  /api/v1/health                      liveness + db + worker heartbeat
GET  /api/v1/hardware                    current probe
GET  /api/v1/lab/runtimes                discovered runtimes + capabilities
GET  /api/v1/lab/models
POST /api/v1/lab/benchmarks              {stage, targets[], workloads[]} -> benchmark_run
GET  /api/v1/lab/benchmarks/{id}         + /events (SSE)
GET  /api/v1/lab/recommendations?goal=
POST /api/v1/lab/models/pull             explicit, requires {confirm_bytes}
POST/GET /api/v1/populations[/{id}[/versions]]  + /import /export
POST/GET /api/v1/experiments[/{id}]
POST /api/v1/experiments/{id}/runs       -> run (manifest frozen)
POST /api/v1/runs/{id}/(pause|resume|cancel)
GET  /api/v1/runs/{id}                   state, counts, rate, ETA (null if unreliable)
GET  /api/v1/runs/{id}/events            SSE, resumable via Last-Event-ID
GET  /api/v1/runs/{id}/trials?cursor=    paginated, filterable
GET  /api/v1/runs/{id}/results           computed analysis
POST /api/v1/runs/{id}/report; GET /api/v1/reports/{id}[.html|.md|.json]
```
Schemas are Pydantic v2 models; OpenAPI → generated TypeScript client (CI checks drift). Errors use RFC 9457 problem JSON.

## 6. Progress/ETA honesty
Denominator = planned trials (known once planned). ETA = remaining ÷ rolling median throughput over the last N minutes, shown as a range, and `null` (indeterminate UI) until ≥ a minimum sample exists. Benchmarks and model pulls report real byte/trial counts or are indeterminate.

## 7. Sleep and resources
`simulacra up --keep-awake` (opt-in) wraps the worker in `caffeinate -i -w <pid>` (process-scoped, auto-released). Docs state plainly that closing the lid or system sleep halts inference. Worker checks free disk and memory pressure between batches and auto-pauses with an event if thresholds trip.

## 8. Statistics stance
Primary outputs: counts, proportions, treatment differences with effect sizes. For intervals, use bootstrap/Wilson **labeled as "sampling variation of this simulation," never human uncertainty**. Multiple-comparison correction when many segments are compared; segment cuts below a minimum n are suppressed. Model-disagreement and repeat-run variation are first-class report sections.
