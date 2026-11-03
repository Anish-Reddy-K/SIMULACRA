# Experiments, trials and reports

## Trial design (ADR-0005)
One trial is one independent, stateless LLM call for a (persona, treatment, repeat). The prompt puts the shared offer text first and the persona card last so runtimes that cache prompt prefixes can reuse the offer. The model returns a schema-validated `ConceptReaction`: `purchase_intent` (5 levels), `appeal` (1-5), `top_benefit`, `top_objection` (reason codes) and a one-sentence `reason`. Deterministic code owns persona sampling, treatment assignment, planning, validation and every statistic.

- **Assignment**: between-subjects assignment is a seeded hash of (seed, persona), independent of run order; within-subjects runs show every persona every treatment as separate independent calls.
- **Invalid output**: validated strictly, retried once with a different seed, then recorded as `invalid_json` / `schema_mismatch` / `request_failed` and counted. Never repaired.
- **Raw evidence**: each trial stores the full prompt, raw output, parsed result, token counts and latency. Trial inserts are idempotent (`UNIQUE(run, persona, treatment, repeat)`) and are committed in the same transaction as their batch.
- **Manifest**: frozen when a run starts: experiment and treatments, population version and spec hash, runtime version, model digest and quantization, structured mode, temperature, seed, prompt version and hash, planned trials, hardware snapshot.

## Analysis (`analysis/concept.py`)
Counts, intent distributions, top-2-box (probably or definitely) with Wilson intervals (described as sampling variation of the simulation, not uncertainty about real people), mean appeal, ranked objections and benefits, segment breakdowns (segments under 10 valid responses are suppressed and expose no numbers), deterministic representative quotes linked to their source trial, and contradiction checks (high appeal with low intent, segments diverging by 20+ points from the overall share). Tests recompute every statistic independently from the raw rows (the claim audit).

## Reports (`reporting/build.py`)
Executive summary (sentences generated from computed numbers, no LLM), research question, population, configuration, model and runtime, findings, segments, treatments, objections, quotes with trial links, contradictions, limitations, suggested real-world follow-up, reproducibility metadata. Exports: Markdown, self-contained HTML (text escaped), JSON.

## Verified run
100 real trials, population of 100 personas with model-written biographies, llama.cpp b11960 serving Qwen2.5 3B Q4_K_M, concurrency 4, batch size 10: 100 of 100 valid, 0 errors, 120 s wall time (about 50 valid trials/min with ~294 prompt and ~69 completion tokens per trial, lower than the benchmark's 95/min because the persona cards here are larger). Result for the example offer: 5% top-2-box, 84% price objections. The report is in `docs/examples/`. An independent SQL recomputation of the headline numbers matched exactly.

This small model rarely expressed purchase intent. That is a finding about the model and prompt, not about people; the validation phase studies such artifacts.
