from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from simulacra import __version__
from simulacra.jobs import queue

router = APIRouter()


class DatabaseHealth(BaseModel):
    ok: bool
    journal_mode: str | None


class WorkerHealth(BaseModel):
    status: Literal["running", "not_running"]
    heartbeat_age_s: float | None = None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: DatabaseHealth
    worker: WorkerHealth


@router.get("/health")
def health(request: Request) -> Health:
    try:
        with request.app.state.engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        db = DatabaseHealth(ok=True, journal_mode=str(mode))
    except SQLAlchemyError:
        db = DatabaseHealth(ok=False, journal_mode=None)
    worker = WorkerHealth(status="not_running")
    if db.ok:
        with request.app.state.sessions() as session:
            alive = queue.worker_alive(session)
            if alive is not None:
                worker = WorkerHealth(
                    status="running", heartbeat_age_s=round(queue.now() - alive.heartbeat_at, 1)
                )
    return Health(
        status="ok" if db.ok else "degraded", version=__version__, database=db, worker=worker
    )
