# Hardware and runtime compatibility

## Tested
| Component | Tested configuration |
|---|---|
| Machine | Apple M4 (10 cores, 4 performance), 16 GB unified memory, macOS 26.5, Metal 4 |
| Runtimes | Ollama 0.15.2, llama.cpp b11960 (`llama-server`, Homebrew 0.8.0), mlx-lm and vllm-mlx (installed with `uv tool`) |
| Models | Qwen2.5 3B and 1.5B Instruct (Q4_K_M GGUF; 4-bit MLX conversion of the 3B) |
| Python / Node | Python 3.12 (pinned by uv), Node 24+ |

Everything else is **untested**. Notes by area:

- **Other Apple Silicon Macs.** Expected to work; throughput scales with memory bandwidth and GPU cores. A 16 GB machine ran the 3B model with 12 server slots (5 GB server memory) but was under memory pressure while other applications were open. With 8 GB, use a 1.5B-class model and fewer slots.
- **Intel Macs, Linux, Windows.** The API, worker, population and analysis code are portable Python, and CI runs on Linux. Hardware detection is most complete on macOS (it reads `sysctl`, `pmset`, `system_profiler`); fields it cannot read are reported as unknown rather than guessed. NVIDIA GPU detection and CUDA runtimes are not implemented. Not tested on Windows.
- **Newer Ollama versions.** Ollama added an MLX backend and parallelism improvements after 0.15.2; its results here (serialized requests, about a quarter of llama.cpp's throughput on the same weights) may not hold for newer versions. Re-run the Inference Lab.
- **vllm-metal.** Not supported: it is a plugin needing a matching vLLM core build and its documented installer is curl-to-bash, which Simulacra will not automate. See `docs/runtimes.md`.

## Resource guidance (measured on the M4)
- Disk: models are 1 to 3 GB each for the sizes tested; the database grows about 3.6 KB per trial (37 MB for 10,000 trials). macOS swap can consume several GB of disk under memory pressure.
- Memory: the 3B model server used 2.4 GB with 4 slots and 5.0 GB with 12 slots; Simulacra's own processes used under 200 MB.
- Sleep: inference stops when the Mac sleeps. Use `simulacra up --keep-awake` (process-scoped `caffeinate`) and stay plugged in; closing the lid still sleeps the machine unless an external display and power are connected.

## Adding a runtime
Any server that speaks `/v1/chat/completions` works through the generic adapter. Add its binary name to `simulacra/inference/discovery.py` to have it detected. Test whether it enforces JSON schemas: the Lab measures this and falls back to prompted JSON (still strictly validated) when it does not.
