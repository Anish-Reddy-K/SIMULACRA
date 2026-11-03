import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulacra.api.app import create_app
from simulacra.config import Settings

MOCK = {"base_url": "mock://", "model": "mock-model"}


@pytest.fixture
def mclient(tmp_path: Path) -> Iterator[TestClient]:
    s = Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "none", enable_mock_backend=True)
    with TestClient(create_app(s), base_url="http://localhost") as c:
        yield c


def wait_done(c: TestClient, run_id: int, timeout: float = 60) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        detail = c.get(f"/api/v1/lab/benchmarks/{run_id}").json()
        if detail["run"]["status"] != "running":
            return detail
        time.sleep(0.1)
    raise AssertionError("benchmark did not finish")


def test_hardware_endpoint(mclient: TestClient) -> None:
    hw = mclient.get("/api/v1/lab/hardware").json()
    assert hw["ram_total_mb"] > 0 and "arch" in hw


def test_full_quick_benchmark_flow_with_mock(mclient: TestClient) -> None:
    r = mclient.post("/api/v1/lab/benchmarks", json={"stage": "quick", "targets": [MOCK]})
    assert r.status_code == 202
    run_id = r.json()["id"]
    detail = wait_done(mclient, run_id)
    assert detail["run"]["status"] == "completed"
    assert {x["workload"] for x in detail["results"]} == {"compat", "B", "E", "F"}
    assert any("Finished" in e for e in detail["events"])
    assert detail["hardware"]["ram_total_mb"] > 0  # exact configuration/hardware recorded

    b = next(x for x in detail["results"] if x["workload"] == "B")
    assert b["metrics"]["valid_rate"] == 1.0 and b["workload_hash"] and b["evidence"] == "quick"
    samples = mclient.get(f"/api/v1/lab/benchmarks/{run_id}/results/{b['id']}/samples").json()
    assert samples and samples[0]["status"] == "valid" and samples[0]["text"]

    assert mclient.get("/api/v1/lab/benchmarks").json()[0]["id"] == run_id
    # Mock measurements are never turned into recommendations.
    recs = mclient.get("/api/v1/lab/recommendations").json()
    assert len(recs) == 6 and all(x["selected"] is None for x in recs)
    mocked = mclient.get("/api/v1/lab/recommendations?include_mock=true").json()
    assert any(x["selected"] for x in mocked)


def test_unreachable_target_is_a_failed_run_not_a_crash(mclient: TestClient) -> None:
    r = mclient.post(
        "/api/v1/lab/benchmarks",
        json={"stage": "screen", "targets": [{"base_url": "http://127.0.0.1:9", "model": "x"}]},
    )
    detail = wait_done(mclient, r.json()["id"])
    assert detail["run"]["status"] == "failed"
    assert any("Could not reach" in e for e in detail["events"])


def test_only_one_run_at_a_time_and_cancel(mclient: TestClient) -> None:
    r = mclient.post(
        "/api/v1/lab/benchmarks", json={"stage": "soak", "soak_seconds": 60, "targets": [MOCK]}
    )
    run_id = r.json()["id"]
    assert (
        mclient.post(
            "/api/v1/lab/benchmarks", json={"stage": "screen", "targets": [MOCK]}
        ).status_code
        == 409
    )
    assert mclient.post(f"/api/v1/lab/benchmarks/{run_id}/cancel").status_code == 200
    assert wait_done(mclient, run_id)["run"]["status"] == "cancelled"
    assert mclient.post(f"/api/v1/lab/benchmarks/{run_id}/cancel").status_code == 409


def test_mock_target_rejected_when_disabled(client: TestClient) -> None:
    r = client.post("/api/v1/lab/benchmarks", json={"stage": "screen", "targets": [MOCK]})
    assert r.status_code == 422


def test_sse_stream_replays_events_and_ends(mclient: TestClient) -> None:
    run_id = mclient.post(
        "/api/v1/lab/benchmarks", json={"stage": "screen", "targets": [MOCK]}
    ).json()["id"]
    wait_done(mclient, run_id)
    with mclient.stream("GET", f"/api/v1/lab/benchmarks/{run_id}/events") as resp:
        body = "".join(resp.iter_text())
    assert "event: log" in body and "Benchmark completed" in body and "event: progress" in body
    first_id = int(body.split("id: ")[1].split("\n")[0])
    with mclient.stream(
        "GET", f"/api/v1/lab/benchmarks/{run_id}/events", headers={"Last-Event-ID": str(first_id)}
    ) as resp:
        resumed = "".join(resp.iter_text())
    assert f"id: {first_id}\n" not in resumed and "Benchmark completed" in resumed


def test_policy_roundtrip(mclient: TestClient) -> None:
    default = mclient.get("/api/v1/lab/policy").json()
    assert default["min_valid_rate"] == 0.9
    default["min_valid_rate"] = 0.8
    assert mclient.put("/api/v1/lab/policy", json=default).status_code == 200
    assert mclient.get("/api/v1/lab/policy").json()["min_valid_rate"] == 0.8


def test_cross_origin_write_is_rejected(mclient: TestClient) -> None:
    body = {"stage": "screen", "targets": [MOCK]}
    evil = mclient.post(
        "/api/v1/lab/benchmarks", json=body, headers={"Origin": "https://evil.example"}
    )
    assert evil.status_code == 403
    other_port = mclient.post(
        "/api/v1/lab/benchmarks", json=body, headers={"Origin": "http://localhost:9999"}
    )
    assert other_port.status_code == 403
    ok = mclient.post(
        "/api/v1/lab/benchmarks", json=body, headers={"Origin": "http://localhost:8765"}
    )
    assert ok.status_code == 202


def test_runs_orphaned_by_a_crash_are_marked_failed_on_startup(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "none")
    with TestClient(create_app(s), base_url="http://localhost") as c:
        from simulacra.benchmarks import repository as repo

        with c.app.state.sessions() as session:  # type: ignore[attr-defined]
            run_id = repo.create_run(session, "quick", {}, {"targets": []})
    with TestClient(create_app(s), base_url="http://localhost") as c2:
        run = c2.get(f"/api/v1/lab/benchmarks/{run_id}").json()["run"]
        assert run["status"] == "failed" and "interrupted" in run["error"]
