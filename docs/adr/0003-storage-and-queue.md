# ADR-0003: SQLite (WAL) as store and job queue; defer DuckDB/Polars

**Status:** Accepted

## Decision
- **SQLite in WAL mode**, one DB file, accessed via **SQLAlchemy 2.x + Alembic**. `busy_timeout` set, short write transactions, `synchronous=NORMAL`.
- **Queue is a table.** Claim = `BEGIN IMMEDIATE; UPDATE jobs SET state='leased', lease_owner=?, lease_expires=? WHERE id=(SELECT ... ORDER BY priority, id LIMIT 1) RETURNING *`. Heartbeat extends the lease; an expired lease makes the job reclaimable. Work unit is a **batch of trials** (e.g. 50), not one trial, so claim overhead is negligible.
- **Idempotent commits:** `trials` has `UNIQUE(run_id, persona_id, treatment_id, repeat_idx)`; results are `INSERT ... ON CONFLICT DO NOTHING`. A crashed-and-retried batch cannot double-count.
- Writes from the worker are batched per N trials in one transaction.

## Challenge to the spec: DuckDB + Polars
10,000 trials × ~1 KB is ~10 MB. SQLite aggregates over that in milliseconds. DuckDB and Polars add two binary dependencies with no measured benefit **at MVP scale**. Decision: **do not add them in Phases 1–9.** Use SQL plus plain Python/NumPy/SciPy for stats. Re-evaluate in Phase 10 (clustering, cross-experiment comparisons) with a measured query-time benchmark; DuckDB can `ATTACH` the SQLite file or read Parquet exports without a schema change, so deferring is free.

## Rejected
- Redis/Celery/Kafka (explicit non-goals; extra processes, no need).
- Postgres (install burden for a local tool).
- Vector DB (structured reason codes first; ADR to revisit in Phase 10).

## Risks
Single-writer contention between API and worker: mitigated by WAL + short transactions; covered by a failure-injection test in Phase 6.

## Outcome (Phase 9)
DuckDB and Polars were never needed. 10,000 trials cost 37 MB and the full analysis of a 10,000-trial run takes 0.6 s in plain Python over SQLite, so the deferral stands.
