from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs import queue
from simulacra.jobs.resources import ResourceGuard, Thresholds
from simulacra.persistence.models import Run, RunEvent


def running_run(s: Session) -> int:
    run = queue.create_run(s, "demo", "r", [{"idx": i} for i in range(4)], {}, 2)
    assert queue.claim_next(s, "w", 60) is not None  # queued -> running
    return run.id


def test_low_disk_pauses_running_runs_with_a_reason(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    with sessions() as s:
        rid = running_run(s)
        guard = ResourceGuard(tmp_path, Thresholds(min_disk_mb=1e12, check_every_s=0))
        reasons = guard.check(s)
        assert reasons and "free disk space" in reasons[0]
        run = s.get(Run, rid)
        assert run is not None and run.state in ("pausing", "paused")
        msgs = [e.message for e in s.scalars(select(RunEvent).where(RunEvent.kind == "resource"))]
        assert any("Paused automatically" in m and "disk" in m for m in msgs)
        queue.control(s, rid, "resume")  # reversible
        assert s.get(Run, rid).state == "running"  # type: ignore[union-attr]


def test_sustained_low_memory_pauses_but_a_single_dip_does_not(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    with sessions() as s:
        rid = running_run(s)
        guard = ResourceGuard(
            tmp_path,
            Thresholds(min_available_mb=1e12, low_memory_checks=3, check_every_s=0, min_disk_mb=0),
        )
        assert guard.check(s) == [] and guard.check(s) == []
        assert s.get(Run, rid).state == "running"  # type: ignore[union-attr]
        reasons = guard.check(s)
        assert reasons and "available memory" in reasons[0]
        assert s.get(Run, rid).state in ("pausing", "paused")  # type: ignore[union-attr]


def test_healthy_machine_is_left_alone_and_reports_resources(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    with sessions() as s:
        rid = running_run(s)
        guard = ResourceGuard(
            tmp_path,
            Thresholds(min_disk_mb=0, min_available_mb=0, check_every_s=0, report_every_s=0),
        )
        assert guard.check(s) == []
        assert s.get(Run, rid).state == "running"  # type: ignore[union-attr]
        events = [e.message for e in s.scalars(select(RunEvent).where(RunEvent.kind == "resource"))]
        assert events and "MB memory available" in events[0]


def test_guard_is_rate_limited(sessions: sessionmaker[Session], tmp_path: Path) -> None:
    with sessions() as s:
        running_run(s)
        guard = ResourceGuard(tmp_path, Thresholds(min_disk_mb=1e12, check_every_s=3600))
        assert guard.check(s, now_s=10_000.0) != []
        assert guard.check(s, now_s=10_001.0) == []  # inside the interval: not checked again
