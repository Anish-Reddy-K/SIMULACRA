import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs import queue
from simulacra.persistence.models import Job, Run, RunEvent, RunUnit

from .conftest import ThreadWorker


def wait_state(
    sessions: sessionmaker[Session], run_id: int, states: tuple[str, ...], timeout: float = 30
) -> str:
    end = time.time() + timeout
    while time.time() < end:
        with sessions() as s:
            run = s.get(Run, run_id)
            state = run.state if run else ""
        if state in states:
            return state
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never reached {states}")


def new_run(sessions: sessionmaker[Session], units: int, batch: int = 5, **cfg: Any) -> int:
    with sessions() as s:
        return queue.create_run(s, "demo", "t", [{"idx": i} for i in range(units)], cfg, batch).id


def unit_count(sessions: sessionmaker[Session], run_id: int) -> int:
    with sessions() as s:
        return (
            s.scalar(select(func.count()).select_from(RunUnit).where(RunUnit.run_id == run_id)) or 0
        )


def test_run_completes_with_every_unit_once(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 53, 5)
    start_worker()
    assert wait_state(sessions, run_id, ("completed",)) == "completed"
    with sessions() as s:
        idxs = sorted(s.scalars(select(RunUnit.unit_idx).where(RunUnit.run_id == run_id)))
        assert idxs == list(range(53))
        run = s.get(Run, run_id)
        assert run is not None and run.done_units == 53 and run.finished_at is not None
        msgs = [e.message for e in s.scalars(select(RunEvent).where(RunEvent.run_id == run_id))]
        assert any("Run started" in m for m in msgs) and any("completed" in m for m in msgs)


def test_unit_errors_complete_with_errors(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 10, 5, error_units=[3, 7])
    start_worker()
    assert wait_state(sessions, run_id, ("completed_with_errors",)) == "completed_with_errors"
    with sessions() as s:
        assert s.get(Run, run_id).error_units == 2  # type: ignore[union-attr]


def test_failing_batch_is_retried_then_succeeds(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 10, 5, fail_batches={"1": 2})  # fails twice, ok on 3rd attempt
    start_worker()
    assert wait_state(sessions, run_id, ("completed",)) == "completed"
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.run_id == run_id, Job.batch_idx == 1)).one()
        assert job.attempts == 3 and job.state == "done"
        assert (
            sum(
                "attempt" in e.message
                for e in s.scalars(select(RunEvent).where(RunEvent.kind == "retry"))
            )
            >= 2
        )


def test_batch_that_always_fails_ends_completed_with_errors(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 10, 5, fail_batches={"1": 99})
    start_worker()
    assert wait_state(sessions, run_id, ("completed_with_errors",)) == "completed_with_errors"
    assert unit_count(sessions, run_id) == 5  # batch 0 only


def test_pause_resume_and_cancel(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 60, 3, sleep_s=0.02)
    start_worker()
    wait_for_units(sessions, run_id, 6)
    with sessions() as s:
        queue.control(s, run_id, "pause")
    assert wait_state(sessions, run_id, ("paused",)) == "paused"
    paused_at = unit_count(sessions, run_id)
    time.sleep(0.5)
    assert unit_count(sessions, run_id) == paused_at  # nothing runs while paused
    assert 0 < paused_at < 60

    with sessions() as s:
        queue.control(s, run_id, "resume")
    wait_for_units(sessions, run_id, paused_at + 6)
    with sessions() as s:
        queue.control(s, run_id, "cancel")
    assert wait_state(sessions, run_id, ("cancelled",)) == "cancelled"
    final = unit_count(sessions, run_id)
    time.sleep(0.4)
    assert unit_count(sessions, run_id) == final < 60


def wait_for_units(
    sessions: sessionmaker[Session], run_id: int, n: int, timeout: float = 30
) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if unit_count(sessions, run_id) >= n:
            return
        time.sleep(0.02)
    raise AssertionError("units did not progress")


def test_graceful_shutdown_releases_unfinished_batch(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 20, 10, sleep_s=0.3)  # batch takes ~3 s
    w = start_worker(grace_s=0.2)
    time.sleep(0.8)  # mid-batch
    w.stop()
    with sessions() as s:
        jobs = list(s.scalars(select(Job).where(Job.run_id == run_id).order_by(Job.batch_idx)))
        assert jobs[0].state == "pending" and jobs[0].attempts == 0 and jobs[0].lease_owner is None
        assert s.get(Run, run_id).state == "running"  # type: ignore[union-attr]
    start_worker()  # a new worker picks the work up and finishes it
    assert wait_state(sessions, run_id, ("completed",), 60) == "completed"
    assert unit_count(sessions, run_id) == 20


def test_two_workers_share_one_run_without_duplicates(
    sessions: sessionmaker[Session], start_worker: Callable[..., ThreadWorker]
) -> None:
    run_id = new_run(sessions, 200, 4, sleep_s=0.002)
    start_worker()
    start_worker()
    assert wait_state(sessions, run_id, ("completed",)) == "completed"
    with sessions() as s:
        idxs = sorted(s.scalars(select(RunUnit.unit_idx).where(RunUnit.run_id == run_id)))
        assert idxs == list(range(200))
        assert s.get(Run, run_id).done_units == 200  # type: ignore[union-attr]
