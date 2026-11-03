import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from simulacra.api.app import create_app
from simulacra.benchmarks.runner import Target
from simulacra.config import Settings
from simulacra.experiments.handler import ExperimentHandler
from simulacra.inference.mock import MockBackend
from simulacra.jobs.handlers import default_registry
from simulacra.persistence.models import Trial
from tests.jobs.conftest import ThreadWorker

MOCK_TARGET = {"base_url": "mock://", "model": "mock-model"}


@pytest.fixture
def eclient(tmp_path: Path) -> Iterator[TestClient]:
    s = Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "none", enable_mock_backend=True)
    with TestClient(create_app(s), base_url="http://localhost") as c:
        yield c


def start_worker(c: TestClient, registry: dict | None = None) -> ThreadWorker:
    sessions = c.app.state.sessions  # type: ignore[attr-defined]
    reg = registry or default_registry(True, sessions)
    return ThreadWorker(sessions, handlers=reg, poll_s=0.05, lease_s=5.0).start()


def make_population(c: TestClient, size: int = 40) -> int:
    preset = c.get("/api/v1/populations/presets").json()
    return int(
        c.post("/api/v1/populations", json={"spec": {**preset, "size": size, "seed": 4}}).json()[
            "id"
        ]
    )


def make_experiment(c: TestClient, pop_id: int, **over: object) -> dict:
    body = {
        "name": "Concept test",
        "research_question": "Would busy people buy a smart mug?",
        "hypothesis": "Interest is highest among tech adopters.",
        "population_version_id": pop_id,
        "scenario": {
            "product_name": "WarmMug",
            "description": "A self-heating mug that keeps drinks hot for hours.",
            "price_usd": 79,
            "category": "kitchen",
        },
        **over,
    }
    r = c.post("/api/v1/experiments", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def wait_run(c: TestClient, run_id: int, timeout: float = 60) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        run = c.get(f"/api/v1/runs/{run_id}").json()
        if run["state"] in ("completed", "completed_with_errors", "failed", "cancelled"):
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_full_flow_with_mock_backend(eclient: TestClient) -> None:
    pop = make_population(eclient, 40)
    exp = make_experiment(eclient, pop, design="between", repeats=2)
    assert exp["treatments"][0]["label"] == "Baseline"
    w = start_worker(eclient)
    try:
        started = eclient.post(
            f"/api/v1/experiments/{exp['id']}/start",
            json={"target": MOCK_TARGET, "batch_size": 7, "concurrency": 3},
        )
        assert started.status_code == 202 and started.json()["trials_planned"] == 80
        run_id = started.json()["run_id"]
        run = wait_run(eclient, run_id)
    finally:
        w.stop()
    assert run["state"] == "completed" and run["done_units"] == 80

    manifest = eclient.get(f"/api/v1/runs/{run_id}/manifest").json()
    assert manifest["population"]["size"] == 40 and manifest["prompt"]["version"] == "concept-v1"
    assert manifest["inference"]["runtime"] == "mock" and manifest["trials_planned"] == 80
    assert manifest["hardware"]["ram_total_mb"] > 0 and manifest["simulacra_version"]

    res = eclient.get(f"/api/v1/runs/{run_id}/results").json()
    assert res["totals"]["trials"] == 80 and res["totals"]["valid"] == 80
    assert res["treatments"][0]["n_valid"] == 80 and res["treatments"][0]["top2box"]["share"] == 1.0

    page = eclient.get(f"/api/v1/runs/{run_id}/trials?limit=5").json()
    assert page["total"] == 80 and len(page["items"]) == 5
    trial = eclient.get(f"/api/v1/trials/{page['items'][0]['id']}").json()
    assert "WarmMug" in trial["prompt_text"] and "$79" in trial["prompt_text"]
    assert json.loads(trial["raw_output"])["purchase_intent"]
    assert eclient.get("/api/v1/trials/999999").status_code == 404

    rep = eclient.post(f"/api/v1/runs/{run_id}/reports")
    assert rep.status_code == 201
    rid = rep.json()["id"]
    md = eclient.get(f"/api/v1/reports/{rid}/export?format=md").text
    assert "# Concept test" in md and "source trial #" in md
    assert eclient.get(f"/api/v1/reports/{rid}/export?format=html").text.startswith(
        "<!doctype html>"
    )
    data = eclient.get(f"/api/v1/reports/{rid}/export?format=json").json()
    assert data["analysis"]["totals"]["valid"] == 80
    assert eclient.get(f"/api/v1/reports/{rid}").json()["limitations"]
    assert eclient.get("/api/v1/reports").json()[0]["id"] == rid


def test_validation_errors(eclient: TestClient) -> None:
    pop = make_population(eclient, 5)
    bad = eclient.post(
        "/api/v1/experiments",
        json={
            "name": "x",
            "research_question": "q?",
            "population_version_id": 9999,
            "scenario": {"product_name": "P", "description": "a long enough description"},
        },
    )
    assert bad.status_code == 422
    dup = eclient.post(
        "/api/v1/experiments",
        json={
            "name": "x",
            "research_question": "q?",
            "population_version_id": pop,
            "scenario": {"product_name": "P", "description": "a long enough description"},
            "treatments": [{"label": "A"}, {"label": "A"}],
        },
    )
    assert dup.status_code == 422
    exp = make_experiment(eclient, pop)
    assert (
        eclient.post(
            f"/api/v1/experiments/{exp['id']}/start",
            json={"target": {"base_url": "http://127.0.0.1:9", "model": "x"}},
        ).status_code
        == 422
    )
    assert (
        eclient.post("/api/v1/experiments/999/start", json={"target": MOCK_TARGET}).status_code
        == 404
    )
    assert eclient.get("/api/v1/experiments/999").status_code == 404
    assert eclient.get("/api/v1/runs/999/results").status_code == 404


async def _handler_with(backend: MockBackend, sessions, allow: bool = True) -> ExperimentHandler:  # type: ignore[no-untyped-def]
    h = ExperimentHandler(sessions, allow)
    spec = {"base_url": "mock://", "model": "mock-model"}
    key = "mock://|mock-model|constrained"
    h._targets[key] = Target("mock", backend, "mock-model", await backend.info())
    _ = spec
    return h


def test_invalid_model_output_is_recorded_not_repaired(eclient: TestClient) -> None:
    import asyncio

    pop = make_population(eclient, 10)
    exp = make_experiment(eclient, pop)
    sessions = eclient.app.state.sessions  # type: ignore[attr-defined]
    bad = MockBackend(lambda r: "definitely buy it!!")  # never JSON
    handler = asyncio.run(_handler_with(bad, sessions))
    w = start_worker(eclient, {"experiment": handler})
    try:
        run_id = eclient.post(
            f"/api/v1/experiments/{exp['id']}/start", json={"target": MOCK_TARGET}
        ).json()["run_id"]
        run = wait_run(eclient, run_id)
    finally:
        w.stop()
    assert run["state"] == "failed" and run["error_units"] == 10  # nothing valid, nothing hidden
    res = eclient.get(f"/api/v1/runs/{run_id}/results").json()
    assert res["totals"]["valid"] == 0 and res["totals"]["by_status"] == {"invalid_json": 10}
    assert res["totals"]["invalid_rate"] == 1.0
    with sessions() as s:
        t = s.scalars(select(Trial).where(Trial.run_id == run_id)).first()
        assert t is not None and t.attempts == 2 and t.raw_output == "definitely buy it!!"


def test_runtime_failures_are_counted_as_request_failed(eclient: TestClient) -> None:
    import asyncio

    pop = make_population(eclient, 8)
    exp = make_experiment(eclient, pop)
    sessions = eclient.app.state.sessions  # type: ignore[attr-defined]
    down = MockBackend(fail_every=1)
    handler = asyncio.run(_handler_with(down, sessions))
    w = start_worker(eclient, {"experiment": handler})
    try:
        run_id = eclient.post(
            f"/api/v1/experiments/{exp['id']}/start", json={"target": MOCK_TARGET}
        ).json()["run_id"]
        run = wait_run(eclient, run_id, 90)
    finally:
        w.stop()
    res = eclient.get(f"/api/v1/runs/{run_id}/results").json()
    assert res["totals"]["by_status"] == {"request_failed": 8}
    assert run["state"] == "failed"


def test_trial_inserts_are_idempotent_on_replay(eclient: TestClient) -> None:
    """If a batch is replayed (lease lost, crash), trials must not double up."""
    import asyncio

    from simulacra.jobs import queue
    from simulacra.jobs.handlers import BatchContext

    pop = make_population(eclient, 6)
    exp = make_experiment(eclient, pop)
    sessions = eclient.app.state.sessions  # type: ignore[attr-defined]
    ok = MockBackend(
        lambda r: json.dumps(
            {
                "purchase_intent": "probably",
                "appeal": 4,
                "top_benefit": "quality",
                "top_objection": "price",
                "reason": "fine",
            }
        )
    )
    handler = asyncio.run(_handler_with(ok, sessions))
    run_id = asyncio.run(_start(sessions, exp["id"]))
    with sessions() as s:
        first = queue.claim_next(s, "w1", 30)
        assert first is not None
        ctx = BatchContext(first, asyncio.Event())
        results = asyncio.run(handler.process(ctx))
        assert queue.commit_results(s, first, "w1", results, ctx.hooks)
        # Replay the same unit results through a second, forged claim of the same units.
        from simulacra.persistence.models import Job

        job = s.get(Job, first.job_id)
        assert job is not None
        job.state, job.lease_owner = "leased", "w2"
        s.commit()
        ctx2 = BatchContext(first, asyncio.Event())
        results2 = asyncio.run(handler.process(ctx2))
        assert queue.commit_results(s, first, "w2", results2, ctx2.hooks)
        total = s.scalar(select(func.count()).select_from(Trial).where(Trial.run_id == run_id))
        distinct = s.scalar(
            select(func.count(func.distinct(Trial.persona_id))).where(Trial.run_id == run_id)
        )
        assert total == distinct == 6


async def _start(sessions, experiment_id: int) -> int:  # type: ignore[no-untyped-def]
    from simulacra.benchmarks.service import TargetSpec
    from simulacra.experiments import service as svc

    run = await svc.start_run(
        sessions,
        experiment_id,
        svc.StartOptions(target=TargetSpec(**MOCK_TARGET), batch_size=100),
        True,
    )
    return run.id


def test_cross_origin_start_rejected(eclient: TestClient) -> None:
    pop = make_population(eclient, 5)
    exp = make_experiment(eclient, pop)
    r = eclient.post(
        f"/api/v1/experiments/{exp['id']}/start",
        json={"target": MOCK_TARGET},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
