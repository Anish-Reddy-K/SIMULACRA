import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulacra.api.app import create_app
from simulacra.config import Settings
from simulacra.jobs.handlers import DemoHandler
from simulacra.jobs.worker import Worker

from .conftest import ThreadWorker


@pytest.fixture
def rclient(tmp_path: Path) -> Iterator[TestClient]:
    s = Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "none", enable_mock_backend=True)
    with TestClient(create_app(s), base_url="http://localhost") as c:
        yield c


def wait_state(c: TestClient, run_id: int, states: tuple[str, ...], timeout: float = 30) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        run = c.get(f"/api/v1/runs/{run_id}").json()
        if run["state"] in states:
            return run
        time.sleep(0.05)
    raise AssertionError(f"never reached {states}: {run}")


def with_worker(c: TestClient) -> ThreadWorker:
    w = ThreadWorker(c.app.state.sessions, poll_s=0.05, lease_s=5.0)  # type: ignore[attr-defined]
    w.worker = Worker(c.app.state.sessions, {"demo": DemoHandler()}, poll_s=0.05, lease_s=5.0)  # type: ignore[attr-defined]
    return w.start()


def test_demo_runs_disabled_without_mock_flag(client: TestClient) -> None:
    assert client.post("/api/v1/runs/demo", json={"units": 5}).status_code == 404


def test_health_reports_worker_state(rclient: TestClient) -> None:
    assert rclient.get("/api/v1/health").json()["worker"]["status"] == "not_running"
    w = with_worker(rclient)
    try:
        end = time.time() + 10
        while (
            time.time() < end
            and rclient.get("/api/v1/health").json()["worker"]["status"] != "running"
        ):
            time.sleep(0.05)
        worker = rclient.get("/api/v1/health").json()["worker"]
        assert worker["status"] == "running" and worker["heartbeat_age_s"] < 5
    finally:
        w.stop()
    assert rclient.get("/api/v1/health").json()["worker"]["status"] == "not_running"  # stopped flag


def test_run_lifecycle_and_progress_fields(rclient: TestClient) -> None:
    run = rclient.post(
        "/api/v1/runs/demo", json={"units": 40, "batch_size": 4, "config": {"sleep_s": 0.01}}
    ).json()
    assert run["state"] == "queued" and run["total_units"] == 40 and run["eta_s"] is None
    w = with_worker(rclient)
    try:
        done = wait_state(rclient, run["id"], ("completed",))
    finally:
        w.stop()
    assert done["done_units"] == 40 and done["error_units"] == 0 and done["elapsed_s"] > 0
    assert done["rate_per_min"] is None  # only reported while running
    units = rclient.get(f"/api/v1/runs/{run['id']}/units?limit=5").json()["items"]
    assert [u["idx"] for u in units] == [0, 1, 2, 3, 4] and units[0]["payload"] == {"value": 0}
    assert rclient.get("/api/v1/runs").json()[0]["id"] == run["id"]
    assert rclient.get("/api/v1/runs/999").status_code == 404


def test_eta_is_indeterminate_then_available_while_running(rclient: TestClient) -> None:
    run = rclient.post(
        "/api/v1/runs/demo", json={"units": 400, "batch_size": 5, "config": {"sleep_s": 0.01}}
    ).json()
    w = with_worker(rclient)
    try:
        end = time.time() + 20
        seen_eta = None
        while time.time() < end:
            cur = rclient.get(f"/api/v1/runs/{run['id']}").json()
            if cur["state"] == "running" and cur["done_units"] < 15:
                assert cur["eta_s"] is None  # too little data: never invented
            if cur["eta_s"] is not None:
                seen_eta = cur
                break
            time.sleep(0.05)
        assert seen_eta is not None and seen_eta["rate_per_min"] > 0 and seen_eta["eta_s"] > 0
        rclient.post(f"/api/v1/runs/{run['id']}/cancel")
        wait_state(rclient, run["id"], ("cancelled",))
    finally:
        w.stop()


def test_controls_and_invalid_transitions(rclient: TestClient) -> None:
    run = rclient.post(
        "/api/v1/runs/demo", json={"units": 100, "batch_size": 2, "config": {"sleep_s": 0.02}}
    ).json()
    rid = run["id"]
    w = with_worker(rclient)
    try:
        wait_state(rclient, rid, ("running",))
        assert rclient.post(f"/api/v1/runs/{rid}/pause").status_code == 200
        wait_state(rclient, rid, ("paused",))
        assert rclient.post(f"/api/v1/runs/{rid}/pause").status_code == 409
        assert rclient.post(f"/api/v1/runs/{rid}/resume").json()["state"] == "running"
        assert rclient.post(f"/api/v1/runs/{rid}/cancel").status_code == 200
        final = wait_state(rclient, rid, ("cancelled",))
        assert final["done_units"] < 100
        assert rclient.post(f"/api/v1/runs/{rid}/resume").status_code == 409
        assert rclient.post(f"/api/v1/runs/{rid}/explode").status_code == 404
        assert rclient.post("/api/v1/runs/999/pause").status_code == 404
    finally:
        w.stop()


def test_sse_replays_history_resumes_and_ends(rclient: TestClient) -> None:
    run = rclient.post("/api/v1/runs/demo", json={"units": 10, "batch_size": 5}).json()
    w = with_worker(rclient)
    try:
        wait_state(rclient, run["id"], ("completed",))
    finally:
        w.stop()
    with rclient.stream("GET", f"/api/v1/runs/{run['id']}/events") as r:
        body = "".join(r.iter_text())
    assert "Run started" in body and "completed" in body and "event: progress" in body
    ids = [int(x.split("\n")[0]) for x in body.split("id: ")[1:]]
    assert ids == sorted(ids) and len(ids) >= 3
    with rclient.stream(
        "GET", f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": str(ids[0])}
    ) as r:
        resumed = "".join(r.iter_text())
    assert f"id: {ids[0]}\n" not in resumed and f"id: {ids[-1]}\n" in resumed


def test_cross_origin_control_rejected(rclient: TestClient) -> None:
    run = rclient.post("/api/v1/runs/demo", json={"units": 5}).json()
    r = rclient.post(f"/api/v1/runs/{run['id']}/cancel", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
