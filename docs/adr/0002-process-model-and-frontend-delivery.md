# ADR-0002: Process model and frontend delivery

**Status:** Accepted

## Decision
Two Python processes, one command (`simulacra up`):
1. **API** (FastAPI/uvicorn, 127.0.0.1 only) — serves REST, SSE, and the built frontend.
2. **Worker** — separate persistent process that claims jobs from SQLite and calls the inference router.

A tiny supervisor in `simulacra up` starts/restarts both. The worker must also run standalone (`simulacra worker`) so runs survive an API restart and a browser being closed.

**Frontend: Next.js with `output: 'export'` (static), served by FastAPI.** End users need no Node runtime; there is one origin, so no CORS; SSE comes straight from FastAPI. Dynamic entities use query params / client routing (`/experiments?id=...`). Dev mode still uses `next dev` with a proxy.

## Why
The spec asks for Next.js but also "ease of use" and "one coherent application". A Node server at runtime doubles install surface for no benefit — we have no SSR/SEO need on a localhost app.

## Rejected
- Next.js server runtime in production (extra process, Node prerequisite).
- Electron/Tauri wrapper (post-MVP packaging question; revisit in Phase 13).
- Celery/Redis (spec non-goal; SQLite queue suffices — ADR-0003).

## Security
Bind 127.0.0.1; reject non-local `Host` headers (DNS-rebinding defense); reject state-changing requests whose `Origin` is not localhost on the Simulacra or dev-server port (implemented instead of the per-install token: browsers always send `Origin` on cross-site writes, so no secret has to be stored or delivered to the UI); no CORS headers are sent.

## Reconsider when
We need server-side rendering or multi-user hosting.
