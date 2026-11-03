import asyncio
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.benchmarks.service import TargetSpec
from simulacra.persistence.models import PersonaRow, Population, PopulationVersion
from simulacra.populations import io as pio
from simulacra.populations import service as svc
from simulacra.populations.context import build_card
from simulacra.populations.presets import ASSUMED_ADULTS
from simulacra.populations.spec import PopulationSpec

router = APIRouter(prefix="/populations")


def _sessions(request: Request) -> sessionmaker[Session]:
    return request.app.state.sessions  # type: ignore[no-any-return]


class EnrichRequest(BaseModel):
    target: TargetSpec
    concurrency: int = 1


class CreatePopulation(BaseModel):
    spec: PopulationSpec
    population_id: int | None = None
    enrich: EnrichRequest | None = None


class VersionOut(BaseModel):
    id: int
    population_id: int
    name: str
    version: int
    status: str
    source: str
    size: int
    seed: int
    created_at: str
    progress_done: int
    progress_total: int
    error: str | None
    enrichment: dict[str, Any]


def _out(v: PopulationVersion, name: str) -> VersionOut:
    created = (
        v.created_at
        if v.created_at.tzinfo
        else v.created_at.replace(tzinfo=__import__("datetime").UTC)
    )
    return VersionOut(
        id=v.id,
        population_id=v.population_id,
        name=name,
        version=v.version,
        status=v.status,
        source=v.source,
        size=v.size,
        seed=v.seed,
        created_at=created.isoformat(),
        progress_done=v.progress_done,
        progress_total=v.progress_total,
        error=v.error,
        enrichment=v.enrichment_json,
    )


def _get(s: Session, version_id: int) -> tuple[PopulationVersion, Population]:
    v = s.get(PopulationVersion, version_id)
    pop = s.get(Population, v.population_id) if v else None
    if v is None or pop is None:
        raise HTTPException(404, "No such population version")
    return v, pop


@router.get("/presets")
def presets() -> dict[str, object]:
    """Illustrative starting spec. Not census data."""
    return ASSUMED_ADULTS


@router.post("", status_code=201)
async def create(body: CreatePopulation, request: Request) -> VersionOut:
    state = request.app.state
    if (
        body.enrich
        and body.enrich.target.base_url == "mock://"
        and not state.settings.enable_mock_backend
    ):
        raise HTTPException(422, "The mock backend is disabled.")
    sessions = _sessions(request)

    def work() -> VersionOut:
        with sessions() as s:
            try:
                v = svc.create_generated(
                    s,
                    body.spec,
                    body.population_id,
                    body.enrich.model_dump() if body.enrich else None,
                )
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            return _out(v, body.spec.name)

    out = await asyncio.to_thread(work)
    if body.enrich:
        task = asyncio.create_task(
            svc.run_enrichment(
                sessions,
                out.id,
                body.enrich.target,
                max(1, min(body.enrich.concurrency, 8)),
                state.settings.enable_mock_backend,
            )
        )
        state.population_tasks[out.id] = task
    return out


@router.get("")
def list_versions(request: Request) -> list[VersionOut]:
    with _sessions(request)() as s:
        rows = s.execute(
            select(PopulationVersion, Population.name)
            .join(Population, Population.id == PopulationVersion.population_id)
            .order_by(PopulationVersion.id.desc())
        ).all()
        return [_out(v, name) for v, name in rows]


class VersionDetail(BaseModel):
    version: VersionOut
    spec: dict[str, Any]
    diagnostics: dict[str, Any] | None


@router.get("/versions/{version_id}")
def detail(version_id: int, request: Request) -> VersionDetail:
    with _sessions(request)() as s:
        v, pop = _get(s, version_id)
        return VersionDetail(
            version=_out(v, pop.name), spec=v.spec_json, diagnostics=v.diagnostics_json
        )


class PersonaPage(BaseModel):
    total: int
    items: list[dict[str, Any]]


@router.get("/versions/{version_id}/personas")
def personas(
    version_id: int, request: Request, offset: int = 0, limit: int = 50, q: str | None = None
) -> PersonaPage:
    limit = max(1, min(limit, 200))
    with _sessions(request)() as s:
        _get(s, version_id)
        cond = [PersonaRow.version_id == version_id]
        if q:
            like = f"%{q}%"
            cond.append(
                or_(
                    PersonaRow.name.ilike(like),
                    PersonaRow.bio.ilike(like),
                    PersonaRow.synthetic_id.ilike(like),
                )
            )
        total = s.scalar(select(func.count()).select_from(PersonaRow).where(*cond)) or 0
        rows = s.scalars(
            select(PersonaRow).where(*cond).order_by(PersonaRow.idx).offset(offset).limit(limit)
        )
        return PersonaPage(total=total, items=[svc.persona_dict(r) for r in rows])


@router.get("/versions/{version_id}/personas/{synthetic_id}/card")
def card(
    version_id: int, synthetic_id: str, request: Request, max_tokens: int = 300
) -> dict[str, Any]:
    with _sessions(request)() as s:
        _get(s, version_id)
        row = s.scalar(
            select(PersonaRow).where(
                PersonaRow.version_id == version_id, PersonaRow.synthetic_id == synthetic_id
            )
        )
        if row is None:
            raise HTTPException(404, "No such persona")
        text = build_card(svc.persona_dict(row), max_tokens=max(50, min(max_tokens, 2000)))
        return {"card": text, "approx_tokens": -(-len(text) // 4)}


@router.get("/versions/{version_id}/export")
def export(
    version_id: int, request: Request, format: Literal["jsonl", "csv"] = "jsonl"
) -> Response:
    with _sessions(request)() as s:
        v, pop = _get(s, version_id)
        if v.status != "ready":
            raise HTTPException(409, "This version is not ready yet")
        rows = [
            svc.persona_dict(r)
            for r in s.scalars(
                select(PersonaRow)
                .where(PersonaRow.version_id == version_id)
                .order_by(PersonaRow.idx)
            )
        ]
        header = {
            "name": pop.name,
            "version": v.version,
            "seed": v.seed,
            "size": v.size,
            "spec": v.spec_json,
            "note": "Synthetic personas. Not real people.",
        }
    if format == "csv":
        body, media, ext = pio.export_csv(rows), "text/csv", "csv"
    else:
        body, media, ext = pio.export_jsonl(header, rows), "application/x-ndjson", "jsonl"
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="population-{version_id}.{ext}"'},
    )


@router.post("/import", status_code=201)
async def import_population(request: Request, name: str = "Imported population") -> VersionOut:
    raw = await request.body()
    try:
        header, records = pio.parse_jsonl(raw)
    except pio.ImportError_ as exc:
        raise HTTPException(422, str(exc)) from exc
    clean = name.strip()[:80] or "Imported population"
    with _sessions(request)() as s:
        v = svc.create_imported(s, clean, header, records)
        return _out(v, clean)
