# ADR-0006: Persona generation pipeline

**Status:** Accepted

## Decision
Structure first, language second:
1. **Population spec** (YAML/JSON, versioned): marginal distributions per attribute, optional correlation targets, strata/weights, seed.
2. **Sampling:** seeded NumPy; correlations via a **Gaussian copula** (handles mixed categorical/ordinal/continuous; simple, inspectable). Hard constraints (e.g. income ↔ employment, age ↔ education minimums) enforced by deterministic rules + rejection sampling.
3. **Enrichment:** the LLM writes biography, brand attitudes, and quirks **conditioned on the sampled attributes**, never the attributes themselves. Output is schema-validated and checked against the sampled facts (contradiction detector).
4. **Diagnostics:** duplicate/near-duplicate detection (n-gram/MinHash), realized-vs-target marginals, correlation error, categorical coverage, bio-length/lexical diversity.
5. **Persist** as immutable `population_versions`; personas are never edited in place.
6. **Compact context builder:** per-experiment, relevance-filtered card (target ≲ 300 tokens, a budget to be validated in Phase 4/9).

## Honesty constraints
Marginals come from the user or from clearly cited public aggregates; the UI labels populations as "assumed distribution," never "representative." LLM-enriched details are flagged as model-generated.

## Evidence this matters
Park et al. (2024): agents built from rich interviews matched participants at ~0.85 normalized accuracy vs ~0.70–0.71 for demographic/persona-description agents — thin personas are weak. Pew (Sept 2026): "digital twins" missed human answers by ~12 points on average and collapsed opinion diversity. Both argue for diversity diagnostics and prominent limitations, not for hiding the weakness. (Figures are from secondary summaries; primary papers to be re-read when writing evaluation docs.)

## Rejected
- Asking an LLM to invent 10,000 biographies unstructured (duplication, mode collapse, no auditability).
