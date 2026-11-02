# Runtime compatibility (verified Nov 2026, Apple M4, 16 GB)

What was actually run against the `OllamaBackend` / `OpenAICompatBackend` adapters in Phase 3. "Verified" means a real request was made on this machine. These are compatibility facts, not benchmarks (see Phase 4 for measurements).

| Runtime | Version | Adapter | Verified | Structured JSON | Timings reported | Notes |
|---|---|---|---|---|---|---|
| Ollama | 0.15.2 (pre-MLX engine) | `OllamaBackend` | yes | constrained (`format`) | prefill/decode/load | Model loads on first request (cold start measured separately). Newer versions (MLX preview, 0.19+) not tested. |
| llama.cpp `llama-server` | 0.8.0 / b11960 (Homebrew) | `OpenAICompatBackend` (auto-detected via `/props`) | yes | constrained (`response_format`) | prefill/decode | Reports slots and per-slot context. `-c` is divided across `-np` slots. Can serve the same GGUF Ollama stores, giving a like-for-like comparison. |
| mlx-lm `mlx_lm.server` | installed via `uv tool` | `OpenAICompatBackend` | yes | **ignored** (schema not enforced) | none | Use `constrained=False` (prompted schema, strict validation). Has `--decode-concurrency` / `--prompt-concurrency` batching flags. |
| vllm-mlx | installed via `uv tool` | `OpenAICompatBackend` | yes | constrained | none | `--continuous-batching` flag. First request is slow (warmup). |
| vllm-metal | 0.1.0 | none | **no** | unknown | unknown | pip-installable plugin that pulls torch and needs a matching vLLM core build; its documented installer is curl-to-bash, which Simulacra will not automate. Revisit when a plain wheel route is verified. |

## Findings that shaped the design
1. **Never assume constrained decoding.** mlx-lm silently ignores `response_format`; the same prompt produced non-conforming JSON until the schema was described in the prompt. Capabilities start as `unknown` and only a probe can set them.
2. **Timings differ by runtime.** Ollama and llama-server report prefill/decode timings; mlx-lm and vllm-mlx do not, so tokens/s for those must be derived client-side (Phase 4 records which method was used).
3. **Cold start is a first-class measurement.** A first Ollama request included ~8 s of model loading in time-to-first-token.

## Reproducing the integration tests
```sh
ollama pull qwen2.5:1.5b
SIMULACRA_REAL_INFERENCE=1 uv run pytest tests/inference/test_real_runtimes.py
```
