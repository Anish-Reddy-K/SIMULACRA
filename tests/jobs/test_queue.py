import threading
import time

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs import queue
from simulacra.persistence.models import Job, Run, RunUnit


def make_run(s: Session, units: int = 10, batch: int = 5, **kw: object) -> Run:
    return queue.create_run(s, "demo", "t", [{"idx": i} for i in range(units)], {}, batch, **kw)  # type: ignore[arg-type]


def test_create_run_batches_and_state(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 11, 5)
        assert run.state == "queued" and run.total_units == 11
        assert s.scalar(select(func.count()).select_from(Job).where(Job.run_id == run.id)) == 3
        held = make_run(s, 3, 5, start=False)
        assert held.state == "created"


def test_claim_order_and_state_transition(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        a, b = make_run(s, 10, 5), make_run(s, 5, 5)
        got = [queue.claim_next(s, "w1", 30) for _ in range(4)]
        first_three = [c for c in got[:3] if c is not None]
        assert [(c.run_id, c.batch_idx) for c in first_three] == [(a.id, 0), (a.id, 1), (b.id, 0)]
        assert got[3] is None
        assert s.get(Run, a.id).state == "running"  # type: ignore[union-attr]


def test_concurrent_claims_never_duplicate(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        make_run(s, 400, 2)  # 200 batches
    claimed: list[int] = []
    lock = threading.Lock()

    def grab(name: str) -> None:
        with sessions() as s:
            while (c := queue.claim_next(s, name, 30)) is not None:
                with lock:
                    claimed.append(c.job_id)

    threads = [threading.Thread(target=grab, args=(f"w{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claimed) == 200 and len(set(claimed)) == 200


def test_paused_and_cancelling_runs_are_not_claimable(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s)
        queue.control(s, run.id, "pause")  # queued -> paused immediately (nothing live)
        assert s.get(Run, run.id).state == "paused"  # type: ignore[union-attr]
        assert queue.claim_next(s, "w", 30) is None
        queue.control(s, run.id, "resume")
        assert queue.claim_next(s, "w", 30) is not None


def test_heartbeat_and_lost_lease(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        make_run(s)
        c = queue.claim_next(s, "w1", 1)
        assert c is not None
        assert queue.heartbeat(s, c.job_id, "w1", 60)
        assert not queue.heartbeat(s, c.job_id, "other", 60)
        s.execute(update(Job).where(Job.id == c.job_id).values(lease_expires=time.time() - 1))
        s.commit()
        c2 = queue.claim_next(s, "w2", 30)  # reclaimed by another worker
        assert c2 is not None and c2.job_id == c.job_id and c2.attempts == 2
        assert not queue.heartbeat(s, c.job_id, "w1", 60)  # w1 lost it


def test_commit_is_idempotent_and_rejects_stale_worker(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 5, 5)
        c1 = queue.claim_next(s, "w1", 30)
        assert c1 is not None
        s.execute(update(Job).where(Job.id == c1.job_id).values(lease_expires=time.time() - 1))
        s.commit()
        c2 = queue.claim_next(s, "w2", 30)
        assert c2 is not None
        results = [(i, "ok", {"v": i}) for i in range(5)]
        assert queue.commit_results(s, c2, "w2", results) is True
        # The original worker finishes late: must be rejected, and must not double-count.
        assert queue.commit_results(s, c1, "w1", results) is False
        assert queue.commit_results(s, c2, "w2", results) is False  # replay of a finished batch
        assert (
            s.scalar(select(func.count()).select_from(RunUnit).where(RunUnit.run_id == run.id)) == 5
        )
        assert s.get(Run, run.id).done_units == 5  # type: ignore[union-attr]


def test_unit_unique_key_blocks_duplicate_rows(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 2, 2)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        queue.commit_results(s, c, "w", [(0, "ok", {}), (0, "ok", {"dup": True}), (1, "ok", {})])
        assert (
            s.scalar(select(func.count()).select_from(RunUnit).where(RunUnit.run_id == run.id)) == 2
        )


def test_retry_then_permanent_failure(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 2, 2, max_attempts=2)
        c = queue.claim_next(s, "w", 30)
        assert c and queue.fail_attempt(s, c, "w", "boom") == "retry"
        c = queue.claim_next(s, "w", 30)
        assert c and c.attempts == 2
        assert queue.fail_attempt(s, c, "w", "boom") == "failed"
        queue.settle_runs(s)
        assert s.get(Run, run.id).state == "failed"  # type: ignore[union-attr]  # nothing succeeded


def test_final_attempt_lease_expiry_fails_the_batch(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 2, 2, max_attempts=1)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        s.execute(update(Job).where(Job.id == c.job_id).values(lease_expires=time.time() - 1))
        s.commit()
        assert queue.claim_next(s, "w2", 30) is None
        queue.settle_runs(s)
        job = s.scalars(select(Job).where(Job.run_id == run.id)).one()
        assert job.state == "failed" and "lease expired" in (job.last_error or "")
        assert s.get(Run, run.id).state == "failed"  # type: ignore[union-attr]


def test_release_does_not_burn_an_attempt(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        make_run(s, 2, 2)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        queue.release(s, c.job_id, "w")
        again = queue.claim_next(s, "w2", 30)
        assert again is not None and again.attempts == 1


def test_control_state_machine(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        run = make_run(s, 10, 5)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        assert queue.control(s, run.id, "pause").state == "pausing"  # a live batch exists
        queue.settle_runs(s)
        assert s.get(Run, run.id).state == "pausing"  # type: ignore[union-attr]
        queue.commit_results(s, c, "w", [(i, "ok", {}) for i in range(5)])
        queue.settle_runs(s)
        assert s.get(Run, run.id).state == "paused"  # type: ignore[union-attr]
        assert queue.control(s, run.id, "resume").state == "running"
        with pytest.raises(queue.ControlError):
            queue.control(s, run.id, "start")
        assert queue.control(s, run.id, "cancel").state == "cancelling"
        queue.settle_runs(s)
        assert s.get(Run, run.id).state == "cancelled"  # type: ignore[union-attr]
        assert (
            s.scalars(select(Job).where(Job.run_id == run.id, Job.state == "pending")).first()
            is None
        )
        with pytest.raises(queue.ControlError):
            queue.control(s, run.id, "pause")
        with pytest.raises(LookupError):
            queue.control(s, 999, "pause")


def test_completion_states(sessions: sessionmaker[Session]) -> None:
    with sessions() as s:
        ok = make_run(s, 2, 2)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        queue.commit_results(s, c, "w", [(0, "ok", {}), (1, "ok", {})])
        queue.settle_runs(s)
        assert s.get(Run, ok.id).state == "completed"  # type: ignore[union-attr]

        mixed = make_run(s, 2, 2)
        c = queue.claim_next(s, "w", 30)
        assert c is not None
        queue.commit_results(s, c, "w", [(0, "ok", {}), (1, "error", {})])
        queue.settle_runs(s)
        r = s.get(Run, mixed.id)
        assert r is not None and r.state == "completed_with_errors" and r.error_units == 1
