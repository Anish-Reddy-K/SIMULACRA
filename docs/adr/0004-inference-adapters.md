# ADR-0004: Inference adapters

**Status:** Proposed (Phase 0). Facts below are from vendor docs/secondary sources and **must be verified on the M4 in Phase 3**.

## Findings (research, Nov 2026)
| Runtime | Relevant facts | Concern |
|---|---|---|
| **Ollama** | Local API, model management, structured outputs via JSON schema. Since 0.19 (Mar 2026) Apple Silicon uses an **MLX backend (preview)**. | One blog claims MLX only auto-enables with ≥32 GB; unconfirmed — test on 16 GB. Parallelism/batching behavior must be measured. |
| **llama.cpp `llama-server`** | `--parallel N` slots, continuous batching, prompt cache, JSON-schema→GBNF constrained decoding, Metal. | Context is divided across slots. Not installed here (needs `brew install llama.cpp`, user action). |
| **mlx-lm** | Apple-native, OpenAI-compatible `mlx_lm.server`. | Server-side batching support unconfirmed. |
| **vllm-mlx** (community) | Continuous batching, prefix caching, OpenAI API. Vendor figures ~3–4× throughput at 5–16 concurrent, **but** one independent test reported per-request decode dropping sharply under batching. | Young, fast-moving version numbers, single maintainer-ish. |
| **vllm-metal** (vllm-project, community plugin) | MLX compute backend under vLLM. PyPI wheel 0.1.0 for CPython 3.12; install via curl-to-bash script; last push May 2026. | Maturity unclear; curl-to-bash installer conflicts with our "no silent installs" rule. |

## Decision
Define one `InferenceBackend` protocol (`discover()`, `list_models()`, `health()`, `generate(request) -> Result`, `capabilities`). Ship **two adapter classes**:
1. `OllamaBackend` (native `/api/chat`, `format=<json schema>`, reports eval/prompt token timings).
2. `OpenAICompatBackend` (any `/v1/chat/completions` server; `response_format` JSON schema where supported, with capability probing). This single class covers llama-server, mlx-lm, vllm-mlx, vllm-metal — "supported" means *probed and benchmarked*, not hardcoded.

Backends differ by **detection profile**, not by code. The spec's "no adapter to inflate the count" rule is thereby honored.

**Phase 4 acceptance minimum on this machine:** Ollama vs. llama-server (GGUF/Metal), plus mlx-lm or vllm-mlx if it installs cleanly.

## Structured-output policy
Prefer server-side constrained decoding. Always validate with Pydantic after; invalid output is recorded (`invalid_json`), retried per policy, and counted in reliability metrics. Never silently repair.

## Rejected
- Writing our own inference runtime (non-goal).
- Per-runtime adapter classes for all five (duplicate code, same HTTP shape).
- Auto-installing runtimes. We detect and *instruct*; installs are user actions.

## Reconsider when
A runtime offers an in-process API with materially better throughput than HTTP (measured).
