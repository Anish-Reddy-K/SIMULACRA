# ADR-0001: Toolchain, runtime versions, repo layout

**Status:** Accepted

## Context
Dev machine: Apple M4, 16 GB, macOS 26.5, **system Python is 3.14.2**, Node 26, `uv` and `npm` present, `pnpm` absent. vllm-metal's published wheel targets CPython 3.12; MLX and many ML wheels lag new CPython releases.

## Decision
- **Python 3.12, pinned via `uv`** (`.python-version`), independent of system Python. Revisit when 3.13/3.14 wheels exist for every runtime we touch.
- **uv workspace** for Python; **npm** for the frontend (no extra install step for contributors; pnpm adds nothing we need).
- Layout: the spec's tree, but **one Python package `simulacra`** with subpackages (`personas, experiments, inference, benchmarks, simulation, analysis, reporting, persistence, api, worker`) rather than separate distributions under `packages/`. Split only if a real boundary appears.
- Lint/type: Ruff + **mypy strict** on `simulacra` (Pyright is faster but mypy has the better Pydantic/SQLAlchemy plugin story). Frontend: ESLint, `tsc --noEmit`, Vitest, Playwright.

## Rejected
- Multiple Python distributions (premature; slows contributors).
- Poetry/pip-tools (uv is faster and already installed).

## Reconsider when
A runtime adapter needs an incompatible Python, or a second deployable emerges.
