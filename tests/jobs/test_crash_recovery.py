"""Failure injection with real processes: kill -9 the worker mid-run and recover."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs import queue
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine
from simulacra.persistence.models import Job, Run, RunUnit, WorkerRow


def spawn_worker(data_dir: Path, lease_s: float = 2.0) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "SIMULACRA_DATA_DIR": str(data_dir),
        "SIMULACRA_ENABLE_MOCK_BACKEND": "true",
        "SIMULACRA_WORKER_LEASE_S": str(lease_s),
    }
    return subprocess.Popen([sys.executable, "-m", "simulacra.cli", "worker"], env=env)


def setup(tmp_path: Path) -> tuple[sessionmaker[Session], Path]:
    data = tmp_path / "data"
    data.mkdir()
    url = f"sqlite:///{data / 'simulacra.db'}"
    migrate.upgrade(url)
    return sessionmaker(make_engine(url), expire_on_commit=False), data


def units(sessions: sessionmaker[Session], run_id: int) -> int:
    with sessions() as s:
        return (
            s.scalar(select(func.count()).select_from(RunUnit).where(RunUnit.run_id == run_id)) or 0
        )


def wait(pred, timeout: float = 60.0) -> None:  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.1)
    raise AssertionError("condition not reached")


def test_kill_9_worker_then_recover_with_no_loss_or_duplicates(tmp_path: Path) -> None:
    sessions, data = setup(tmp_path)
    with sessions() as s:
        run_id = queue.create_run(
            s, "demo", "crash", [{"idx": i} for i in range(120)], {"sleep_s": 0.01}, batch_size=10
        ).id
    first = spawn_worker(data)
    try:
        wait(lambda: units(sessions, run_id) >= 20)
        first.send_signal(signal.SIGKILL)  # no cleanup, no goodbye
        first.wait(timeout=10)
        mid = units(sessions, run_id)
        assert 0 < mid < 120
        with sessions() as s:
            leased = s.scalars(select(Job).where(Job.run_id == run_id, Job.state == "leased")).all()
            assert leased, "the killed worker should have left a leased batch behind"
            assert s.get(Run, run_id).state == "running"  # type: ignore[union-attr]

        second = spawn_worker(data)  # a fresh worker; the dead lease expires after ~2 s
        try:
            wait(lambda: _state(sessions, run_id) == "completed", 90)
        finally:
            second.send_signal(signal.SIGTERM)
            second.wait(timeout=30)
    finally:
        if first.poll() is None:
            first.kill()
    with sessions() as s:
        idxs = sorted(s.scalars(select(RunUnit.unit_idx).where(RunUnit.run_id == run_id)))
        assert idxs == list(range(120))  # nothing lost, nothing duplicated
        run = s.get(Run, run_id)
        assert run is not None and run.done_units == 120 and run.error_units == 0
        assert any(
            j.attempts > 1 for j in s.scalars(select(Job).where(Job.run_id == run_id))
        )  # recovered


def _state(sessions: sessionmaker[Session], run_id: int) -> str:
    with sessions() as s:
        return s.get(Run, run_id).state  # type: ignore[union-attr]


def test_sigterm_stops_worker_gracefully_and_marks_it_stopped(tmp_path: Path) -> None:
    sessions, data = setup(tmp_path)
    proc = spawn_worker(data)
    try:
        wait(lambda: _worker_rows(sessions) == 1)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
    with sessions() as s:
        assert s.scalars(select(WorkerRow)).one().stopped is True


def _worker_rows(sessions: sessionmaker[Session]) -> int:
    with sessions() as s:
        return s.scalar(select(func.count()).select_from(WorkerRow)) or 0


def test_two_worker_processes_contend_on_one_database(tmp_path: Path) -> None:
    sessions, data = setup(tmp_path)
    with sessions() as s:
        run_id = queue.create_run(
            s, "demo", "contend", [{"idx": i} for i in range(300)], {"sleep_s": 0.001}, batch_size=5
        ).id
    procs = [spawn_worker(data, lease_s=10) for _ in range(2)]
    try:
        wait(lambda: _state(sessions, run_id) == "completed", 90)
    finally:
        for p in procs:
            p.send_signal(signal.SIGTERM)
        for p in procs:
            p.wait(timeout=30)
    with sessions() as s:
        idxs = sorted(s.scalars(select(RunUnit.unit_idx).where(RunUnit.run_id == run_id)))
        assert idxs == list(range(300))
        assert s.scalar(select(func.count()).select_from(WorkerRow)) == 2
