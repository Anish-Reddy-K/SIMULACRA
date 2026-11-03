.PHONY: setup dev up build dist check py-check web-check e2e audit

setup:
	uv sync
	cd apps/web && npm ci

# Development: API on :8765 and Next dev server on :3000 (proxies /api to the API).
dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run simulacra up & \
	(cd apps/web && npm run dev) & \
	wait

# Production shape: build the static UI, then serve everything from the API on :8765.
build:
	cd apps/web && npm run build

# Wheel with the UI bundled: `pip install dist/simulacra-*.whl && simulacra up`
dist: build
	rm -rf src/simulacra/web && cp -R apps/web/out src/simulacra/web
	uv build --wheel --out-dir dist
	rm -rf src/simulacra/web

up: build
	uv run simulacra up

py-check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest -q

web-check:
	cd apps/web && npm run lint && npm run typecheck && npm test && npm run build

check: py-check web-check

e2e: build
	cd apps/web && npm run test:e2e

# Production dependencies only for npm; dev-only lint tooling is tracked separately.
audit:
	uv run pip-audit
	cd apps/web && npm audit --omit=dev --audit-level=high
