# Durable execution

Long runs survive closing the browser, restarting the API and crashing the worker. The design is a database-backed queue (ADR-0003) with a separate worker process.

## Moving parts
- **API process** (`simulacra up`): creates runs, serves progress, never executes work.
- **Worker process** (`simulacra worker`, also started and restarted by `simulacra up`): claims batches, runs them via a handler for the run's `kind`, commits results. Several workers may run against one database.
- **SQLite tables**: `runs`, `jobs` (one leased batch each), `run_units` (one row per finished unit), `run_events` (append-only, the source for SSE), `workers` (heartbeats).

## Run states
`created`, `queued`, `preparing`, `running`, `pausing`, `paused`, `cancelling`, `cancelled`, `completed`, `completed_with_errors`, `failed`. Transitions live in `jobs/queue.py` (`control`, `settle_runs`) and are covered by tests. `failed` means no unit finished; `completed_with_errors` means some units errored or some batches failed permanently.

## Guarantees and how they are enforced
- **No duplicate claims**: a batch is claimed by one atomic `UPDATE ... RETURNING` (tested with 8 concurrent threads over 200 batches, and with two worker processes).
- **Crash recovery**: a worker holds a lease it extends every `lease/3` seconds. If it dies (tested with `kill -9`), the lease expires and any worker re-claims the batch, up to `max_attempts` (default 3), after which the batch fails permanently and the run ends `completed_with_errors` or `failed`.
- **Idempotent commits**: finishing a batch and inserting its results happen in one transaction guarded by lease ownership; `(run_id, unit_idx)` is unique and inserts use `ON CONFLICT DO NOTHING`. A late worker whose lease was lost cannot commit, and replays cannot double-count (tested).
- **Retries**: a failing batch returns to `pending` and is retried; each attempt is logged as a `retry` event.
- **Graceful shutdown**: on SIGTERM the worker stops claiming, gives the current batch a grace period, then releases it without burning an attempt and exits (tested).
- **Pause**: stops new claims and waits for in-flight batches to finish, so pause latency is up to one batch. **Cancel** does the same, then marks remaining batches cancelled. **Resume** continues from stored progress (no work is repeated because finished batches are `done`).
- **Progress**: persisted events plus a snapshot over Server-Sent Events, resumable with `Last-Event-ID`. The ETA is derived from units committed in the last two minutes and is `null` (shown as "estimating...") until at least five units exist; nothing is invented.

## Known limitations
- Pause and cancel latency is bounded by batch duration (batch size is chosen per run kind).
- A single SQLite writer is shared by API and workers; short transactions and WAL keep contention low, and a two-process contention test passes, but extreme write rates would need batching larger units.
- If the machine sleeps, inference stops; leases expire and work resumes after wake-up.
- Disk-space and memory-pressure auto-pause are not implemented yet (planned with the experiment runner in Phase 7/9).
