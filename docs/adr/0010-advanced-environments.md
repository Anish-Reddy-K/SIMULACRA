# ADR-0010: Advanced simulation environments (multi-step, memory, social)

**Status:** Accepted for Phase 12: evaluated, deliberately not built.

## Context
The plan allows multi-step scenarios, persistent memory, relationships, social interaction, customer journeys, environment controllers and branchable worlds, "only what provides demonstrated value".

## Evidence gathered (Phases 4 to 11)
- **Stateless trials already show weak behavioral grounding.** In real runs, small local models failed basic invariants (an affluent persona at $50 never chose to buy; price sensitivity was not detectable at n=100 per arm; run-to-run and model-to-model agreement were limited, see `docs/evaluation/`). Adding memory and interaction multiplies the surface for model artifacts while the base signal is still unvalidated.
- **Cost.** Multi-step journeys multiply inference calls per persona by the number of steps. At the measured 60 to 110 valid trials per minute, a five-step journey for 10,000 personas would take about 8 to 14 hours instead of about 2.
- **No validated question needs it.** The three shipped experiment types answer concrete questions with one decision per persona.
- **Integrity risk.** State transitions driven by model narration violate the rule that deterministic code owns rules and state.

## Decision
Do not implement multi-step scenarios, persistent memory, relationships, social influence or branchable worlds now. What exists and is sufficient for today's requirements: identity (immutable, versioned populations), per-trial state (stored prompts and outputs), repeats (run-to-run variation), and within-subjects designs.

## Design sketch if reconsidered
A deterministic environment controller owns state (budgets, exposure counts, inventory); a persona's state is a versioned snapshot keyed by (run, persona, step); treatments branch by copying snapshots; every step is a normal leased unit so durability, retries and reports are unchanged.

## Reconsider when
A real-data evaluation shows the single-step simulation is calibrated well enough that sequential effects are the next source of error, or a user-defined study cannot be expressed as repeated independent decisions.
