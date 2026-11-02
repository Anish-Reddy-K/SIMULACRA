# Simulacra

Local-first platform for simulating experiments with thousands of persistent AI personas on your own hardware. Simulated opinions are not human predictions.

Status: early development (Phase 1, repository foundation). See `docs/` for the architecture and plan.

## Requirements
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically), Node 24+ and npm, `make`.

## Quick start
```sh
make setup   # install Python and web dependencies
make up      # build the UI and serve everything at http://127.0.0.1:8765
```

## Development
```sh
make dev     # API on :8765 and Next dev server on :3000 (open :3000)
make check   # ruff, mypy, pytest, eslint, tsc, vitest, production build
make e2e     # Playwright smoke tests against the real server
make audit   # dependency vulnerability scan
```

The API binds to 127.0.0.1 only and rejects non-local `Host` headers. Data lives in your user data directory (override with `SIMULACRA_DATA_DIR`).

License: Apache-2.0.
