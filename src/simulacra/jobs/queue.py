"""Database-backed durable queue (ADR-0003).

Claiming is a single atomic UPDATE ... RETURNING, so two workers can never claim the same
batch. A worker that dies simply stops extending its lease; the batch becomes claimable again.
Results are committed in the same transaction that finishes the batch, guarded by lease
ownership and unique keys, so a replayed batch cannot double-count.
"""

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from simulacra.persistence.models import Job, Run, RunEvent, RunUnit, WorkerRow

# Run states (docs/phase plan): created, queued, preparing, running, pausing, paused,
# cancelling, cancelled, completed, completed_with_errors, failed.
ACTIVE_STATES = ("queued", "preparing", "running", "pausing", "cancelling")
TERMINAL_STATES = ("completed", "completed_with_errors", "failed", "cancelled")
DEFAULT_BATCH = 25


class ControlError(ValueError):
    """An action is not valid for the run's current state."""


@dataclass
class Claimed:
    job_id: int
    run_id: int
    batch_idx: int
    attempts: int
    payload: dict[str, Any]
    kind: str
    config: dict[str, Any]


def now() -> float:
    return time.time()


def add_event(session: Session, run_id: int, kind: str, message: str) -> None:
    session.add(RunEvent(run_id=run_id, kind=kind, message=message))


def create_run(
    session: Session,
    kind: str,
    name: str,
    units: list[dict[str, Any]],
    config: dict[str, Any],
    batch_size: int = DEFAULT_BATCH,
    max_attempts: int = 3,
    manifest: dict[str, Any] | None = None,
    start: bool = True,
) -> Run:
    """Create a run and its batches. Each unit is a JSON payload with a stable `idx`."""
    run = Run(
        kind=kind,
        name=name,
        state="preparing",
        total_units=len(units),
        config_json=config,
        manifest_json=manifest or {},
    )
    session.add(run)
    session.flush()
    for b, lo in enumerate(range(0, len(units), batch_size)):
        session.add(
            Job(
                run_id=run.id,
                batch_idx=b,
                state="pending",
                max_attempts=max_attempts,
                payload_json={"units": units[lo : lo + batch_size]},
            )
        )
    add_event(session, run.id, "state", f"Prepared {len(units)} units in batches of {batch_size}")
    run.state = "queued" if start else "created"
    session.commit()
    return run


def _expire_exhausted(session: Session, t: float) -> None:
    """Batches whose lease expired after their final attempt fail instead of looping forever."""
    session.execute(
        update(Job)
        .where(Job.state == "leased", Job.lease_expires < t, Job.attempts >= Job.max_attempts)
        .values(state="failed", last_error="lease expired on the final attempt (worker died?)")
    )


def claim_next(session: Session, worker_id: str, lease_s: float) -> Claimed | None:
    t = now()
    _expire_exhausted(session, t)
    row = session.execute(
        text(
            """
            UPDATE jobs SET state='leased', lease_owner=:w, lease_expires=:exp, attempts=attempts+1
            WHERE id = (
              SELECT j.id FROM jobs j JOIN runs r ON r.id = j.run_id
              WHERE r.state IN ('queued','running')
                AND (j.state='pending' OR (j.state='leased' AND j.lease_expires < :now))
              ORDER BY r.id, j.batch_idx LIMIT 1
            )
            RETURNING id, run_id, batch_idx, attempts, payload_json
            """
        ),
        {"w": worker_id, "exp": t + lease_s, "now": t},
    ).first()
    if row is None:
        session.commit()
        return None
    run = session.get(Run, row.run_id)
    assert run is not None  # noqa: S101  (FK guarantees it)
    if run.state == "queued":
        run.state = "running"
        run.started_at = datetime.now(UTC)
        add_event(session, run.id, "state", "Run started")
    payload = (
        row.payload_json if isinstance(row.payload_json, dict) else json.loads(row.payload_json)
    )
    if row.attempts > 1:
        add_event(
            session, run.id, "retry", f"Batch {row.batch_idx} re-claimed (attempt {row.attempts})"
        )
    session.commit()
    return Claimed(
        row.id, row.run_id, row.batch_idx, row.attempts, payload, run.kind, run.config_json
    )


def heartbeat(session: Session, job_id: int, worker_id: str, lease_s: float) -> bool:
    """Extend a lease. False means the lease was lost and the worker must stop this batch."""
    res = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.lease_owner == worker_id, Job.state == "leased")
        .values(lease_expires=now() + lease_s)
    )
    session.commit()
    return bool(cast("CursorResult[Any]", res).rowcount)


def commit_results(
    session: Session,
    claimed: Claimed,
    worker_id: str,
    results: list[tuple[int, str, dict[str, Any]]],
    hooks: Sequence[Callable[[Session], None]] = (),
) -> bool:
    """Atomically store unit results and finish the batch. False if the lease was lost."""
    res = session.execute(
        update(Job)
        .where(Job.id == claimed.job_id, Job.lease_owner == worker_id, Job.state == "leased")
        .values(state="done", lease_owner=None, lease_expires=None)
    )
    if not cast("CursorResult[Any]", res).rowcount:
        session.rollback()
        return False
    t = now()
    for hook in hooks:  # handler-specific rows, written in the same transaction as the batch
        hook(session)
    if results:
        stmt = (
            sqlite_insert(RunUnit)
            .values(
                [
                    {
                        "run_id": claimed.run_id,
                        "unit_idx": idx,
                        "status": status,
                        "payload_json": payload,
                        "created_at": t,
                    }
                    for idx, status, payload in results
                ]
            )
            .on_conflict_do_nothing(index_elements=["run_id", "unit_idx"])
        )
        session.execute(stmt)
    _refresh_counts(session, claimed.run_id)
    session.commit()
    return True


def _refresh_counts(session: Session, run_id: int) -> None:
    done, errors = session.execute(
        text("SELECT COUNT(*), COALESCE(SUM(status='error'),0) FROM run_units WHERE run_id=:r"),
        {"r": run_id},
    ).one()
    session.execute(update(Run).where(Run.id == run_id).values(done_units=done, error_units=errors))


def fail_attempt(session: Session, claimed: Claimed, worker_id: str, error: str) -> str:
    """Record a failed attempt: retry (back to pending) or give up after max attempts."""
    job = session.get(Job, claimed.job_id)
    if job is None or job.lease_owner != worker_id or job.state != "leased":
        session.rollback()
        return "lost"
    job.last_error = error[:500]
    job.lease_owner, job.lease_expires = None, None
    if job.attempts >= job.max_attempts:
        job.state = "failed"
        add_event(
            session,
            claimed.run_id,
            "error",
            f"Batch {claimed.batch_idx} failed permanently: {error[:200]}",
        )
        out = "failed"
    else:
        job.state = "pending"
        add_event(
            session,
            claimed.run_id,
            "retry",
            f"Batch {claimed.batch_idx} attempt {job.attempts} failed: {error[:200]}",
        )
        out = "retry"
    session.commit()
    return out


def release(session: Session, job_id: int, worker_id: str) -> None:
    """Graceful shutdown: hand an unfinished batch back without burning an attempt."""
    session.execute(
        update(Job)
        .where(Job.id == job_id, Job.lease_owner == worker_id, Job.state == "leased")
        .values(state="pending", lease_owner=None, lease_expires=None, attempts=Job.attempts - 1)
    )
    session.commit()


def settle_runs(session: Session) -> None:
    """Advance run states that depend on their batches (called every worker tick).

    A "live" batch has an unexpired lease. Expired leases are reclaimable work, not live.
    """
    t = now()
    _expire_exhausted(session, t)
    runs = session.scalars(select(Run).where(Run.state.in_(("running", "pausing", "cancelling"))))
    for run in list(runs):
        row = session.execute(
            text(
                "SELECT "
                "COALESCE(SUM(state='leased' AND lease_expires >= :t), 0), "
                "COALESCE(SUM(state='pending' OR (state='leased' AND lease_expires < :t)), 0), "
                "COALESCE(SUM(state='failed'), 0) "
                "FROM jobs WHERE run_id = :r"
            ),
            {"r": run.id, "t": t},
        ).one()
        live, reclaimable, failed_jobs = int(row[0]), int(row[1]), int(row[2])
        if run.state == "pausing" and live == 0:
            run.state = "paused"
            add_event(session, run.id, "state", "Run paused")
        elif run.state == "cancelling" and live == 0:
            session.execute(
                update(Job)
                .where(Job.run_id == run.id, Job.state.in_(("pending", "leased")))
                .values(state="cancelled", lease_owner=None, lease_expires=None)
            )
            run.state, run.finished_at = "cancelled", datetime.now(UTC)
            add_event(session, run.id, "state", "Run cancelled")
        elif run.state == "running" and live + reclaimable == 0:
            if failed_jobs == 0 and run.error_units == 0:
                run.state = "completed"
            elif run.done_units - run.error_units == 0:  # nothing succeeded
                run.state = "failed"
            else:
                run.state = "completed_with_errors"
            run.finished_at = datetime.now(UTC)
            add_event(
                session,
                run.id,
                "state",
                f"Run {run.state.replace('_', ' ')}: {run.done_units} of {run.total_units} units, "
                f"{run.error_units} errors, {failed_jobs} failed batches",
            )
    session.commit()


def control(session: Session, run_id: int, action: str) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise LookupError("No such run")
    transitions: dict[str, tuple[tuple[str, ...], str]] = {
        "pause": (("queued", "running"), "pausing"),
        "resume": (("paused", "pausing"), "running"),
        "cancel": (("created", "queued", "running", "pausing", "paused"), "cancelling"),
        "start": (("created",), "queued"),
    }
    if action not in transitions:
        raise ControlError(f"unknown action {action!r}")
    allowed, new = transitions[action]
    if run.state not in allowed:
        raise ControlError(f"cannot {action} a run that is {run.state}")
    if action == "pause" and run.state == "queued":
        new = "paused"
    if action == "cancel" and run.state in ("created", "paused"):
        session.execute(
            update(Job)
            .where(Job.run_id == run.id, Job.state == "pending")
            .values(state="cancelled")
        )
        new = "cancelled"
        run.finished_at = datetime.now(UTC)
    if action == "resume" and run.state == "paused":
        new = "queued" if run.started_at is None else "running"
    run.state = new
    add_event(session, run.id, "state", f"Requested {action}: now {new}")
    session.commit()
    return run


def worker_alive(session: Session, max_age_s: float = 15.0) -> WorkerRow | None:
    t = now()
    return session.scalar(
        select(WorkerRow)
        .where(WorkerRow.stopped.is_(False), WorkerRow.heartbeat_at > t - max_age_s)
        .order_by(WorkerRow.heartbeat_at.desc())
        .limit(1)
    )
