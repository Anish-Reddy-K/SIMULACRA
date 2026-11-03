# Inference Lab: how it works

The Lab answers one question: which local runtime and model run best on this machine, for Simulacra's kind of work. Every recommendation comes from measurements made on this machine. Nothing is estimated, and configurations without measurements are shown as "not benchmarked".

## Stages
| Stage | What runs | Evidence label |
|---|---|---|
| Compatibility | Load the model, 3 tiny structured requests. Measures whether schema output validates. | Compatibility only |
| Quick | Workload B at concurrency 1 and 4, E, and a reduced consistency suite F | Quick (indicative) |
| Detailed | B concurrency sweep (1, 2, 4, 8, 16 while throughput still gains 10 percent or more), 3 repetitions of B at the best level, A, C, D (120 trials), E, full F | Detailed |
| Sustained | Workload G for a chosen duration; per-minute throughput windows and drift | Sustained run |

Skipping is always allowed. Model downloads, runtime installs and runtime starts are never done by Simulacra.

## Workloads
A short classification, B persona decision (primary metric), C long persona card, D batch, E larger nested JSON schema, F behavioral consistency, G sustained mix. Prompts are fixed, versioned code (`simulacra/benchmarks/workloads.py`). Each result stores a content hash of the exact requests, plus all raw trials and responses, so every number can be inspected.

## Metrics (and what they are not)
- Primary: valid structured trials per minute at the best tested concurrency.
- Speed: decode tokens/s (runtime-reported when the runtime provides timings, otherwise derived on the client; the method is stored and shown), prefill tokens/s, TTFT, median and p95 latency, first-request latency.
- Reliability: valid, invalid-JSON, schema-mismatch, failure and timeout rates.
- Resources: peak RSS of the server process tree, lowest system-available memory, swap growth. RSS can under-report Metal allocations on Apple Silicon, so system memory and swap are checked too. GPU utilization is not collected because `powermetrics` needs root.
- Consistency (workload F): deterministic invariants where one exists (budget constraint at $600, price monotonicity, paraphrase invariance, persona-over-injected-instruction, memory-fact recall, affluent responsiveness which guards against an always-refuse model) plus a stability number (repeated-trial agreement) that is reported but not scored because variation can be legitimate.

These are proxy metrics. They do not measure whether responses resemble real people.

## Recommendation policy (`simulacra/benchmarks/recommend.py`, thresholds in `policy.py`)
1. Exclude configurations that failed compatibility screening.
2. Exclude if peak server memory exceeds 60 percent of RAM, system-available memory fell below 500 MB, or swap grew more than 1 GB.
3. Exclude if the valid-output rate is below 90 percent or the request failure rate is above 5 percent.
4. Rank per goal:
   - Fastest: valid trials per minute.
   - Best balanced: 0.4 x relative throughput + 0.3 x valid-output rate + 0.3 x consistency.
   - Highest local quality: consistency, then valid rate, then model size (capacity proxy), then throughput.
   - Overnight: needs a sustained run of at least 300 s with failure rate at most 5 percent and last-window throughput at least 80 percent of the first window. Otherwise the pick is labeled provisional.
   - Low memory: lowest peak server memory.
   - Privacy-first: balanced, restricted to runtimes on this machine.
5. Show every considered option with its status and reason, and when a different choice is better.

Defaults are placeholders set before any baseline existed. They are editable through `GET/PUT /api/v1/lab/policy` and the active policy version is stored with every recommendation. Mock results are excluded from recommendations.

## Fairness
Same prompts, seeds, max output tokens and sampling for every target. Quantizations are recorded, not forced equal: Ollama and llama-server share the same GGUF file, while the MLX runtimes use an MLX 4-bit conversion of the same model, which is not bit-identical. Run one runtime at a time. The exact runtime version, model digest, quantization, structured-output mode, and a hardware snapshot are stored with each run.

## Known limitations
- Concurrency results depend on runtime settings (for example `OLLAMA_NUM_PARALLEL`, llama-server `-np`); the Lab reports what happened with the settings in use and does not change them.
- A detailed run measures the machine as it was at that time; background load affects it.
- Evidence from short sustained runs does not prove overnight stability.
