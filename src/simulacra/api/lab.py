import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.benchmarks import repository as repo
from simulacra.benchmarks.hardware import HardwareProfile, detect_hardware
from simulacra.benchmarks.policy import Policy
from simulacra.benchmarks.recommend import (
    GOALS,
    Goal,
    Recommendation,
    build_evidence,
    recommend,
)
from simulacra.benchmarks.runner import Stage
from simulacra.benchmarks.service import TargetSpec, execute_run, start_hardware_snapshot
from simulacra.inference.discovery import Discovery, RuntimeReport, discover
from simulacra.inference.types import ModelInfo, RuntimeInfo, RuntimeKind
from simulacra.persistence.models import (
    BenchmarkEvent,
    BenchmarkResult,
    BenchmarkRun,
    Setting,
)

router = APIRouter(prefix="/lab")
POLICY_KEY = "lab.policy"


def _sessions(request: Request) -> sessionmaker[Session]:
    return request.app.state.sessions  # type: ignore[no-any-return]


@router.get("/hardware")
def hardware(request: Request) -> HardwareProfile:
    return detect_hardware(request.app.state.settings.data_dir)


def _with_mock(found: Discovery, request: Request) -> Discovery:
    """Tests and demos only: expose the synthetic backend when it is explicitly enabled."""
    if request.app.state.settings.enable_mock_backend:
        found.runtimes.append(
            RuntimeReport(
                base_url="mock://",
                running=True,
                info=RuntimeInfo(kind=RuntimeKind.MOCK, base_url="mock://", version="synthetic"),
                models=[ModelInfo(name="mock-model")],
            )
        )
    return found


@router.get("/runtimes")
async def runtimes(request: Request) -> Discovery:
    """Installed runtime binaries and the servers answering right now."""
    return _with_mock(await discover(), request)


class RuntimeModel(ModelInfo):
    runtime_base_url: str
    runtime_kind: str


@router.get("/models")
async def models(request: Request) -> list[RuntimeModel]:
    found = _with_mock(await discover(), request)
    return [
        RuntimeModel(**m.model_dump(), runtime_base_url=r.base_url, runtime_kind=r.info.kind.value)
        for r in found.runtimes
        if r.running and r.info
        for m in r.models
    ]


class StartBenchmark(BaseModel):
    stage: Stage = "quick"
    targets: list[TargetSpec] = Field(min_length=1, max_length=8)
    soak_seconds: float = Field(300.0, ge=10, le=86_400)


class RunSummary(BaseModel):
    id: int
    stage: str
    status: str
    created_at: str
    finished_at: str | None
    op: str | None
    op_done: int
    op_total: int
    error: str | None
    targets: list[dict[str, Any]]


def _iso(dt: datetime) -> str:
    """SQLite returns naive datetimes; they are stored as UTC, so say so explicitly."""
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).isoformat()


def _summary(run: BenchmarkRun) -> RunSummary:
    return RunSummary(
        id=run.id,
        stage=run.stage,
        status=run.status,
        created_at=_iso(run.created_at),
        finished_at=_iso(run.finished_at) if run.finished_at else None,
        op=run.op,
        op_done=run.op_done,
        op_total=run.op_total,
        error=run.error,
        targets=run.config_json.get("targets", []),
    )


@router.post("/benchmarks", status_code=202)
async def start_benchmark(body: StartBenchmark, request: Request) -> RunSummary:
    state = request.app.state
    if any(not t.done() for t in state.benchmark_tasks.values()):
        raise HTTPException(409, "A benchmark is already running. Wait for it or cancel it.")
    if not state.settings.enable_mock_backend and any(
        t.base_url == "mock://" for t in body.targets
    ):
        raise HTTPException(422, "The mock backend is disabled.")
    sessions = _sessions(request)
    with sessions() as s:
        run_id = repo.create_run(
            s,
            body.stage,
            start_hardware_snapshot(),
            {"targets": [t.model_dump() for t in body.targets], "soak_seconds": body.soak_seconds},
        )
        repo.add_event(
            s, run_id, f"Queued {body.stage} benchmark for {len(body.targets)} target(s)"
        )
    task = asyncio.create_task(
        execute_run(
            sessions,
            run_id,
            body.stage,
            body.targets,
            body.soak_seconds,
            state.settings.enable_mock_backend,
        )
    )
    state.benchmark_tasks[run_id] = task
    with sessions() as s:
        run = s.get(BenchmarkRun, run_id)
        assert run is not None  # noqa: S101
        return _summary(run)


@router.get("/benchmarks")
def list_benchmarks(request: Request) -> list[RunSummary]:
    with _sessions(request)() as s:
        runs = s.scalars(select(BenchmarkRun).order_by(BenchmarkRun.id.desc()).limit(50))
        return [_summary(r) for r in runs]


class ResultOut(BaseModel):
    id: int
    target_label: str
    runtime_kind: str
    runtime_version: str | None
    base_url: str
    model: str
    model_digest: str | None
    quantization: str | None
    structured_mode: str
    stage: str
    evidence: str
    workload: str
    concurrency: int
    workload_hash: str | None
    metrics: dict[str, Any] | None
    diagnostics: list[dict[str, Any]]
    compat: dict[str, Any] | None
    extras: dict[str, Any]


def _result(r: BenchmarkResult) -> ResultOut:
    return ResultOut(
        id=r.id,
        target_label=r.target_label,
        runtime_kind=r.runtime_kind,
        runtime_version=r.runtime_version,
        base_url=r.base_url,
        model=r.model,
        model_digest=r.model_digest,
        quantization=r.quantization,
        structured_mode=r.structured_mode,
        stage=r.stage,
        evidence=r.evidence,
        workload=r.workload,
        concurrency=r.concurrency,
        workload_hash=r.workload_hash,
        metrics=r.metrics_json,
        diagnostics=r.diagnostics_json,
        compat=r.compat_json,
        extras=r.extras_json,
    )


class RunDetail(BaseModel):
    run: RunSummary
    hardware: dict[str, Any]
    results: list[ResultOut]
    events: list[str]


@router.get("/benchmarks/{run_id}")
def get_benchmark(run_id: int, request: Request) -> RunDetail:
    with _sessions(request)() as s:
        run = s.get(BenchmarkRun, run_id)
        if run is None:
            raise HTTPException(404, "No such benchmark run")
        events = s.scalars(
            select(BenchmarkEvent)
            .where(BenchmarkEvent.run_id == run_id)
            .order_by(BenchmarkEvent.id)
        )
        return RunDetail(
            run=_summary(run),
            hardware=run.hardware_json,
            results=[_result(r) for r in repo.results_for_run(s, run_id)],
            events=[f"{e.ts:%H:%M:%S} {e.message}" for e in events],
        )


@router.get("/benchmarks/{run_id}/results/{result_id}/samples")
def get_samples(run_id: int, result_id: int, request: Request) -> list[dict[str, Any]]:
    """Raw per-trial evidence behind a result."""
    with _sessions(request)() as s:
        res = s.get(BenchmarkResult, result_id)
        if res is None or res.run_id != run_id:
            raise HTTPException(404, "No such result")
        return [
            {
                "idx": x.idx,
                "group": x.group,
                "status": x.status,
                "text": x.text,
                "error": x.error,
                "total_ms": x.total_ms,
                "ttft_ms": x.ttft_ms,
                "prompt_tokens": x.prompt_tokens,
                "completion_tokens": x.completion_tokens,
            }
            for x in repo.samples_for_result(s, result_id)
        ]


@router.post("/benchmarks/{run_id}/cancel")
async def cancel_benchmark(run_id: int, request: Request) -> dict[str, str]:
    task = request.app.state.benchmark_tasks.get(run_id)
    if task is None or task.done():
        raise HTTPException(409, "This benchmark is not running")
    task.cancel()
    return {"status": "cancelling"}


@router.get("/benchmarks/{run_id}/events")
async def benchmark_events(run_id: int, request: Request) -> StreamingResponse:
    """Server-Sent Events. Resumable with Last-Event-ID; ends when the run is terminal."""
    sessions = _sessions(request)
    last_id = int(request.headers.get("last-event-id", "0") or 0)

    async def stream() -> AsyncIterator[str]:
        nonlocal last_id
        while True:
            with sessions() as s:
                run = s.get(BenchmarkRun, run_id)
                if run is None:
                    return
                rows = s.scalars(
                    select(BenchmarkEvent)
                    .where(BenchmarkEvent.run_id == run_id, BenchmarkEvent.id > last_id)
                    .order_by(BenchmarkEvent.id)
                ).all()
                for e in rows:
                    last_id = e.id
                    yield f"id: {e.id}\nevent: log\ndata: {json.dumps(e.message)}\n\n"
                progress = {
                    "status": run.status,
                    "op": run.op,
                    "done": run.op_done,
                    "total": run.op_total,
                }
                yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
                finished = run.status in repo.TERMINAL
            if finished and not rows:
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


def _load_policy(s: Session) -> Policy:
    row = s.get(Setting, POLICY_KEY)
    return Policy.model_validate_json(row.value) if row else Policy()


@router.get("/policy")
def get_policy(request: Request) -> Policy:
    with _sessions(request)() as s:
        return _load_policy(s)


@router.put("/policy")
def put_policy(policy: Policy, request: Request) -> Policy:
    with _sessions(request)() as s:
        row = s.get(Setting, POLICY_KEY)
        if row:
            row.value = policy.model_dump_json()
        else:
            s.add(Setting(key=POLICY_KEY, value=policy.model_dump_json()))
        s.commit()
    return policy


@router.get("/recommendations")
def recommendations(request: Request, include_mock: bool = False) -> list[Recommendation]:
    with _sessions(request)() as s:
        policy = _load_policy(s)
        evidence = build_evidence(repo.all_results(s))
    ram = detect_hardware().ram_total_mb
    allow = include_mock and request.app.state.settings.enable_mock_backend
    return [recommend(g, evidence, policy, ram, include_mock=allow) for g in GOALS]


@router.get("/recommendations/{goal}")
def one_recommendation(goal: Goal, request: Request) -> Recommendation:
    return next(r for r in recommendations(request) if r.goal == goal)
