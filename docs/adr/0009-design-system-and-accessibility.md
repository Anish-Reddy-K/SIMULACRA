# ADR-0009: Neumorphic design system with accessibility guardrails

**Status:** Proposed (Phase 0)

## Problem
Classic neumorphism fails WCAG: shadow-only boundaries give controls ~1.2–1.5:1 contrast, and focus/disabled states are indistinguishable.

## Decision
"Soft neumorphic research lab" applied to **surfaces, not information**:
- Raised/inset shadows for panels, cards, and containers. **Interactive controls additionally get a 1–2 px solid border at ≥3:1** against their background (WCAG 1.4.11), a visible 2 px focus ring offset from the surface, and text ≥4.5:1.
- State is never conveyed by shadow alone (icon/label/weight changes for pressed, selected, disabled).
- Warm-neutral base, one restrained accent (deep teal-green, "lab" feel) plus a distinct amber for warnings; no purple gradients.
- Tokens in CSS variables (light + dark); shadows derived from a base color via tokens, not hand-picked per component.
- `prefers-reduced-motion` honored; charts use a validated color-blind-safe palette and direct labels.
- shadcn/ui (Radix) primitives supply keyboard/ARIA behavior; we restyle via tokens rather than forking components.
- Automated: axe-core in Playwright on every main screen plus a contrast-token unit test.

## Rejected
Pure shadow-only controls; glassmorphism; dense dashboards.

## Process note
Phase 2 will use the `ui-ux-pro-max` skill for palette/typography selection and produce 2–3 token candidates for owner review before building.
