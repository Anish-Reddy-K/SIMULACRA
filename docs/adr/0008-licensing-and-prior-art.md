# ADR-0008: Licensing and prior-art boundaries

**Status:** Proposed — **needs owner decision on license**.

## Findings
- **Concordia (Google DeepMind):** Entity-Component architecture; the Game Master is itself an entity (v2.0, Aug 2025); prefabs, engine abstraction. Reported Apache-2.0 — confirm in repo.
- **MiroFish:** seed-document → knowledge graph → persona agents on the OASIS engine → ReportAgent; Zep for memory (Neo4j in the offline fork). Reported **AGPL-3.0** (secondary sources; primary repo not fetched). Great for open-ended social-forecast demos; heavy (graph DB, memory service, two social-platform simulators) for controlled experiments.
- **Generative Agents / 1,000 People (Park et al.):** persona depth drives fidelity (see ADR-0006).

## Decision
- Take **concepts only** from Concordia (agent/environment separation, deterministic resolution of actions, state vs. observation). No code copy; no dependency.
- **Do not copy or derive from MiroFish code** (AGPL would force our license). Clean-room only.
- **Differentiator vs. MiroFish:** controlled experiments (randomized treatments, deterministic rules), local-hardware benchmarking/recommendation, resumable 10k-trial execution, evidence-linked reports, honest validity labeling — not open-ended social-network forecasting.
- **Recommended project license: Apache-2.0** (patent grant, corporate-friendly, compatible with Concordia-style attribution). MIT is the simpler alternative.
- All model licenses are surfaced in the Lab (some local models restrict commercial use); report footers include model + license.
- Run `pip-licenses` / `license-checker` in CI from Phase 1.

## Reconsider when
Primary-source license verification contradicts the secondary reports above.
