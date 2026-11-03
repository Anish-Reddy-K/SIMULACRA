# Contributing

Thanks for helping. Simulacra values the simplest correct solution, honest measurement, and scientific caution. Please read `CLAUDE.md` for the engineering principles and `docs/` for the architecture.

## Setup
```sh
make setup      # uv sync and npm ci (uv installs Python 3.12 automatically)
make check      # ruff, mypy, pytest, eslint, tsc, vitest, production build
make e2e        # Playwright tests against the real server (installs Chromium on first use)
make dev        # API on :8765 and web dev server on :3000
```

## Workflow
- Work on a branch, keep commits small, and use conventional prefixes with a short lowercase message (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Add or update tests for behavior you change. Statistical code needs an independent check (textbook value or an independent computation). UI changes need a Playwright test and an axe accessibility pass.
- Never present unmeasured numbers. Benchmark and performance claims must come from a recorded run.
- Keep the interface free of em dashes (hyphens only); a test enforces this.
- Real-model integration tests are opt-in: `SIMULACRA_REAL_INFERENCE=1 uv run pytest tests/inference/test_real_runtimes.py`.

## Architecture in one paragraph
A FastAPI process serves the API, SSE streams and the static Next.js export. A separate worker process claims leased batches from a SQLite-backed queue and calls local inference runtimes through one adapter interface. Populations are sampled by code and (optionally) enriched by a model. Analysis is deterministic code; the language model only writes qualitative text. See `docs/adr/` for the decisions and their alternatives.
