from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from simulacra import __version__

router = APIRouter()


class DatabaseHealth(BaseModel):
    ok: bool
    journal_mode: str | None


class WorkerHealth(BaseModel):
    # Phase 6 replaces this with real heartbeat data. Until a worker exists, say so.
    status: Literal["not_running"] = "not_running"


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
    return Health(
        status="ok" if db.ok else "degraded",
        version=__version__,
        database=db,
        worker=WorkerHealth(),
    )
