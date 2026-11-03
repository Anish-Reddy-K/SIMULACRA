# Roadmap

Status as of this release: the product concept, ad comparison and pricing workflows are complete and tested end to end. See `docs/` for measured results and limitations.

## Done
Inference Lab (hardware detection, runtime and model discovery, staged benchmarks, behavioral invariants, transparent recommendations), population factory, durable job execution with crash recovery, experiment runner, A/B and pricing statistics, evidence-linked analysis and reports, scaling measurements to 10,000 trials.

## Next (not built)
- Multi-step scenarios, persistent per-persona memory and branchable state (evaluated in `docs/adr/0010-advanced-environments.md`; deferred until a validated need exists).
- Evaluation against real human data on a public dataset (the pipeline and format exist; no real-human results are published yet).
- More runtimes once a plain-wheel install exists (vllm-metal).
- Optional local transcription for dictation (whisper.cpp or MLX Whisper).
- PDF report export.
- Natural-language questions translated into the existing structured queries.

## Explicit non-goals
Unrestricted agent societies, cloud or multi-user hosting, real-person digital twins, and any claim that simulated results predict real human behavior.
