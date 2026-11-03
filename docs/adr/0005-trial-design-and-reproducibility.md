# ADR-0005: Trial design and what "reproducible" means

**Status:** Accepted

## Decision
- **One trial = one stateless LLM call** producing a schema-validated decision for (persona, treatment, repeat). MVP experiments need no inter-agent interaction; this maximizes batchability and prefix-cache hits (shared scenario text first, persona card second, question last).
- **Deterministic code owns:** population sampling, treatment assignment (seeded hash of `run_seed, persona_id`), eligibility/budget checks, outcome computation, all statistics. The LLM supplies only subjective interpretation: stance, intent, reason codes, short rationale.
- **Structured reason codes** (enum + free-text) so qualitative analysis works without embeddings in early phases.
- **State separation:** `Identity` (immutable, versioned), `State` (mutable, branchable — introduced Phase 12), `Trial` (per-run record).

## Reproducibility, stated honestly
Bit-identical regeneration is **not** promised: batching, kernel nondeterminism, and runtime upgrades change outputs even at fixed seed. We promise:
1. **Exact config capture** (execution manifest: model digest, quantization, runtime version, sampling, prompt-template hash, seeds, hardware, concurrency, any adaptive change).
2. **All raw prompts + outputs stored**, so every number is re-derivable from stored data deterministically.
3. **Re-run comparison tooling**: measure run-to-run variation rather than hide it.
A `determinism_check` in Phase 4 measures how often temp=0/fixed-seed repeats match per backend, and the report states it.

## Prompt-injection posture
Imported text (seed docs, product descriptions) is wrapped as delimited data, never merged into system instructions; outputs are schema-constrained, which limits blast radius. Agents have no tools in MVP.

## Rejected
- Free-form multi-turn agent narration as the unit of simulation (unbatchable, unfalsifiable).
- Claiming seed-level determinism.
