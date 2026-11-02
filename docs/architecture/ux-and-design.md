# UX flows and design strategy (Phase 0 proposal)

## Navigation (left rail, collapses to bottom bar on mobile)
Dashboard · Inference Lab · Populations · Experiments · Runs (live) · Reports · Settings

## Core flows
1. **Onboarding (skippable at every step):** Welcome + honesty statement ("simulated opinions, not predictions") → hardware detection (shown locally, nothing sent) → runtimes found/not found (with copy-paste install help, never auto-install) → models found (explicit "download" with size + free disk) → optional quick benchmark (live, real progress) → recommendation with "why" → sample experiment (bundled small population, tiny run) → open first report.
2. **Inference Lab:** Hardware · Runtimes · Models · Benchmark setup · Live progress · Comparison (trials/min, tok/s, memory, valid-rate, consistency, soak) · Recommendations (6 goals, each with rationale, alternatives, caveats, evidence badge) · History.
3. **Experiment builder (wizard):** Question & hypothesis → population (pick/generate) → scenario & treatments → outcome schema & primary metric → model/runtime (prefilled from recommendation; shows estimated time from *measured* throughput, or "unknown") → review frozen manifest → start.
4. **Live monitor:** phase, done/total, rate, elapsed, ETA range, memory, model/runtime, retries, recent errors, current operation; pause/resume/cancel; survives refresh via SSE resume.
5. **Results/Report:** summary first, every number clickable to its trial rows; quotes link to source trial; limitations section is not collapsible away; exports HTML/MD/JSON/CSV.

## Persistent honesty UI
A "Simulated" chip on all result views; the report header states synthetic ≠ observed ≠ calibrated; segment cuts under min-n are greyed out with the reason.

## Visual direction
Warm off-white base (#EFEBE4-ish) and a deep warm-charcoal dark theme; accent deep teal; amber for caution; neutral grey scale for chart ink. Typography: a refined sans for UI plus a monospaced face for numbers/IDs (specific families chosen in Phase 2 with owner review). Raised surfaces for cards, inset for inputs/wells, plus borders/focus rings per ADR-0009. Motion: 120–200 ms ease for state changes only; none under reduced-motion.

## Quality gates (Phase 2+)
Playwright: keyboard-only traversal, axe-core zero serious/critical violations, screenshots at 375/768/1280 px, light + dark.
