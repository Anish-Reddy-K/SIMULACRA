import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs import queue
from simulacra.persistence.models import Job, Run, RunEvent, RunUnit

router = APIRouter(prefix="/runs")
RATE_WINDOW_S = 120.0
MIN_UNITS_FOR_ETA = 20
MIN_ELAPSED_FOR_ETA_S = 10.0  # an early burst of completions says little about the true rate


def _sessions(request: Request) -> sessionmaker[Session]:
    return request.app.state.sessions  # type: ignore[no-any-return]


class RunOut(BaseModel):
    id: int
    kind: str
    name: str
    state: str
    total_units: int
    done_units: int
    error_units: int
    batches_total: int
    batches_failed: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    elapsed_s: float | None
    rate_per_min: float | None  # rolling, from committed units; None until enough data
    eta_s: float | None  # None (indeterminate) until the rate is reliable
    error: str | None


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).isoformat()


def _out(s: Session, run: Run) -> RunOut:
    started = (
        run.started_at.replace(tzinfo=UTC)
        if run.started_at and not run.started_at.tzinfo
        else run.started_at
    )
    finished = (
        run.finished_at.replace(tzinfo=UTC)
        if run.finished_at and not run.finished_at.tzinfo
        else run.finished_at
    )
    end = finished or datetime.now(UTC)
    elapsed = (end - started).total_seconds() if started else None
    rate: float | None = None
    eta: float | None = None
    if run.state == "running" and started is not None:
        t = queue.now()
        since_start = t - started.timestamp()
        window = min(RATE_WINDOW_S, since_start)  # includes startup time: deliberately conservative
        recent = (
            s.scalar(
                select(func.count())
                .select_from(RunUnit)
                .where(RunUnit.run_id == run.id, RunUnit.created_at > t - window)
            )
            or 0
        )
        if recent >= MIN_UNITS_FOR_ETA and since_start >= MIN_ELAPSED_FOR_ETA_S:
            rate = recent / (window / 60)
            eta = (run.total_units - run.done_units) / (rate / 60) if rate > 0 else None
    batches = s.scalar(select(func.count()).select_from(Job).where(Job.run_id == run.id)) or 0
    failed = (
        s.scalar(
            select(func.count()).select_from(Job).where(Job.run_id == run.id, Job.state == "failed")
        )
        or 0
    )
    return RunOut(
        id=run.id,
        kind=run.kind,
        name=run.name,
        state=run.state,
        total_units=run.total_units,
        done_units=run.done_units,
        error_units=run.error_units,
        batches_total=batches,
        batches_failed=failed,
        created_at=_iso(run.created_at) or "",
        started_at=_iso(run.started_at),
        finished_at=_iso(run.finished_at),
        elapsed_s=elapsed,
        rate_per_min=rate,
        eta_s=eta,
        error=run.error,
    )


class CreateDemoRun(BaseModel):
    name: str = "Demo run"
    units: int = Field(ge=1, le=100_000)
    batch_size: int = Field(25, ge=1, le=1000)
    config: dict[str, Any] = {}


@router.post("/demo", status_code=201)
def create_demo(body: CreateDemoRun, request: Request) -> RunOut:
    """Synthetic work for tests and demos. Only available when the mock backend is enabled."""
    if not request.app.state.settings.enable_mock_backend:
        raise HTTPException(404, "Demo runs are disabled")
    with _sessions(request)() as s:
        run = queue.create_run(
            s,
            "demo",
            body.name,
            [{"idx": i} for i in range(body.units)],
            body.config,
            body.batch_size,
        )
        return _out(s, run)


@router.get("")
def list_runs(request: Request) -> list[RunOut]:
    with _sessions(request)() as s:
        return [_out(s, r) for r in s.scalars(select(Run).order_by(Run.id.desc()).limit(100))]


@router.get("/{run_id}")
def get_run(run_id: int, request: Request) -> RunOut:
    with _sessions(request)() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "No such run")
        return _out(s, run)


def _control(run_id: int, action: str, request: Request) -> RunOut:
    with _sessions(request)() as s:
        try:
            run = queue.control(s, run_id, action)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except queue.ControlError as exc:
            raise HTTPException(409, str(exc)) from exc
        return _out(s, run)


# Explicit routes (not /{run_id}/{action}) so other /runs/{id}/... routes can never be shadowed.
@router.post("/{run_id}/pause")
def pause(run_id: int, request: Request) -> RunOut:
    return _control(run_id, "pause", request)


@router.post("/{run_id}/resume")
def resume(run_id: int, request: Request) -> RunOut:
    return _control(run_id, "resume", request)


@router.post("/{run_id}/cancel")
def cancel(run_id: int, request: Request) -> RunOut:
    return _control(run_id, "cancel", request)


@router.get("/{run_id}/units")
def units(run_id: int, request: Request, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    with _sessions(request)() as s:
        if s.get(Run, run_id) is None:
            raise HTTPException(404, "No such run")
        rows = s.scalars(
            select(RunUnit)
            .where(RunUnit.run_id == run_id)
            .order_by(RunUnit.unit_idx)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [
                {"idx": u.unit_idx, "status": u.status, "payload": u.payload_json} for u in rows
            ]
        }


@router.get("/{run_id}/events")
async def events(run_id: int, request: Request) -> StreamingResponse:
    """Server-Sent Events: persisted run events, resumable with Last-Event-ID."""
    sessions = _sessions(request)
    last_id = int(request.headers.get("last-event-id", "0") or 0)

    async def stream() -> AsyncIterator[str]:
        nonlocal last_id
        while True:
            with sessions() as s:
                run = s.get(Run, run_id)
                if run is None:
                    return
                rows = s.scalars(
                    select(RunEvent)
                    .where(RunEvent.run_id == run_id, RunEvent.id > last_id)
                    .order_by(RunEvent.id)
                ).all()
                for e in rows:
                    last_id = e.id
                    yield f"id: {e.id}\nevent: {e.kind}\ndata: {json.dumps(e.message)}\n\n"
                snap = _out(s, run)
                yield f"event: progress\ndata: {snap.model_dump_json()}\n\n"
                finished = run.state in queue.TERMINAL_STATES
            if finished and not rows:
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


_ = time  # keep import for rate helpers used by tests
