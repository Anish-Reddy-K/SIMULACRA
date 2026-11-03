# Measured results: Apple M4, 16 GB, macOS 26.5 (2026-11-02)

Everything below was measured on this machine through the Inference Lab (detailed stage unless noted). Raw data, including every run's configuration, is in `docs/benchmarks/raw/` and in the app's Benchmark history. Model: Qwen2.5 3B Instruct (and 1.5B for one row). Primary workload B: persona purchase decision as schema-constrained JSON, about 300 prompt tokens, 40 to 90 output tokens.

| Configuration | Valid trials/min (best concurrency) | Decode tok/s | Peak server RSS | Valid output | Consistency invariants | Repeat CV |
|---|---|---|---|---|---|---|
| llama.cpp b11960, GGUF Q4_K_M (same file as Ollama), `-np 4` | **95.3** (c=4) | 29 per request (runtime) | 2.7 GB | 100% | 73% | 2.2% |
| mlx-lm, MLX 4-bit, schema in prompt | 43.1 (c=4) | 48 (client-derived) | 1.9 GB | 98.4% | 83% | 0.3% |
| vllm-mlx, MLX 4-bit, constrained | 36.5 (c=2) | not available | 2.6 GB | 100% | 67% | 7.6% |
| Ollama 0.15.2, Q4_K_M | 24.0 (c=1) | 48 (runtime) | 2.4 GB | 100% | 73% | 0.5% |
| Ollama 0.15.2, qwen2.5:1.5b Q4_K_M | 47.6 (c=2) | 88 (runtime) | 1.4 GB | 100% | 68% | 2.0% |

Sustained runs (workload G, 302 s each, actual duration, not an overnight test):
- llama.cpp at concurrency 4: 466 trials, 92.7 valid trials/min, 100% valid, per-minute windows 79, 95, 96, 96, 96 (first minute includes warmup), no swap growth.
- Ollama at concurrency 1: 121 trials, 24.0 valid trials/min, 100% valid, windows 24, 25, 24, 23, 24, no swap growth.

## What this shows
1. **Same weights, 4x difference.** On the identical GGUF file, llama-server with 4 slots delivered about 4x the valid trials per minute of Ollama 0.15.2. Ollama in this version serialized requests (concurrency 2 and 4 gave the same trials/min with proportionally higher latency); llama-server scaled from 32.5 (c=1) to 94.4 (c=4) and plateaued at c=8. Newer Ollama versions were not tested.
2. **Arithmetic, not a measurement:** at these rates 10,000 workload-B-sized trials would take about 1.8 hours on llama.cpp and about 6.9 hours on Ollama. Phase 9 measures real 10,000-trial runs.
3. **Structured output.** Servers that enforce the JSON schema (Ollama, llama.cpp, vllm-mlx) gave 100% valid output. mlx-lm ignores the schema; with the schema described in the prompt it was valid 98.4% overall but only 75% on the larger nested schema (workload E).
4. **Consistency checks flag a weakness in all of these small models.** The "affluent persona at the lowest price buys at least once" check failed for every configuration: none of them ever chose `buy_now` for a wealthy persona at $50. Without this guard, every model would have scored 100% on the budget-constraint checks simply by refusing everything. The persona-over-injected-instruction check failed for vllm-mlx (0%) and partly for the 1.5B model (50%). Memory-fact recall varied by model and quantization (40% to 100%). Sample sizes are small (5 to 12 cases per check), so differences between 67% and 83% are not reliable.
5. **Quality ordering is weak evidence.** The "highest quality" pick (mlx-lm, 83%) rests on a few dozen synthetic cases and one model family. Treat it as a hint to investigate, not a verdict.

## Measurement notes and known issues
- Run 5 (first vllm-mlx run) reported 8,000+ tokens/s decode: vllm-mlx delivers output in one burst, so the client-derived rate was meaningless. That was a bug in the Lab's metric; it now reports "not available" when the decode window is too small, and run 7 is the corrected rerun. Run 5 is kept in `raw/` as a record, and recommendations use the latest run.
- Peak server RSS can under-report Metal memory; system-available memory and swap growth were recorded alongside it (swap growth was 0 in the sustained runs).
- One runtime at a time was resident during each run. The machine was plugged in. Other applications were running.
- mlx-lm and vllm-mlx used an MLX conversion of the model, not the identical GGUF; behavior differences between those rows and the GGUF rows include the quantization difference.
- No GPU utilization numbers (needs root). No overnight run was done in this session.
