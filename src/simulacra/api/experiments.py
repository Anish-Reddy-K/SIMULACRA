import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.analysis import concept
from simulacra.experiments import service as svc
from simulacra.persistence.models import Experiment, Report, Run, Treatment, Trial
from simulacra.reporting import build

router = APIRouter()


def _sessions(request: Request) -> sessionmaker[Session]:
    return request.app.state.sessions  # type: ignore[no-any-return]


class ExperimentOut(BaseModel):
    id: int
    name: str
    kind: str
    research_question: str
    hypothesis: str
    population_version_id: int
    scenario: dict[str, Any]
    config: dict[str, Any]
    treatments: list[dict[str, Any]]
    created_at: str


def _exp_out(s: Session, e: Experiment) -> ExperimentOut:
    ts = s.scalars(select(Treatment).where(Treatment.experiment_id == e.id).order_by(Treatment.idx))
    created = (
        e.created_at
        if e.created_at.tzinfo
        else e.created_at.replace(tzinfo=__import__("datetime").UTC)
    )
    return ExperimentOut(
        id=e.id,
        name=e.name,
        kind=e.kind,
        research_question=e.research_question,
        hypothesis=e.hypothesis,
        population_version_id=e.population_version_id,
        scenario=e.scenario_json,
        config=e.config_json,
        created_at=created.isoformat(),
        treatments=[{"idx": t.idx, "label": t.label, "params": t.params_json} for t in ts],
    )


@router.post("/experiments", status_code=201)
def create_experiment(body: svc.CreateExperiment, request: Request) -> ExperimentOut:
    with _sessions(request)() as s:
        try:
            exp = svc.create_experiment(s, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return _exp_out(s, exp)


@router.get("/experiments")
def list_experiments(request: Request) -> list[ExperimentOut]:
    with _sessions(request)() as s:
        return [
            _exp_out(s, e) for e in s.scalars(select(Experiment).order_by(Experiment.id.desc()))
        ]


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, request: Request) -> ExperimentOut:
    with _sessions(request)() as s:
        exp = s.get(Experiment, experiment_id)
        if exp is None:
            raise HTTPException(404, "No such experiment")
        return _exp_out(s, exp)


class StartedRun(BaseModel):
    run_id: int
    trials_planned: int
    state: str


@router.post("/experiments/{experiment_id}/start", status_code=202)
async def start_experiment(
    experiment_id: int, opts: svc.StartOptions, request: Request
) -> StartedRun:
    settings = request.app.state.settings
    if opts.target.base_url == "mock://" and not settings.enable_mock_backend:
        raise HTTPException(422, "The mock backend is disabled.")
    try:
        run = await svc.start_run(
            _sessions(request), experiment_id, opts, settings.enable_mock_backend
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return StartedRun(run_id=run.id, trials_planned=run.total_units, state=run.state)


@router.get("/runs/{run_id}/results")
def results(run_id: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        try:
            return concept.analyze(s, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/runs/{run_id}/manifest")
def manifest(run_id: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "No such run")
        return run.manifest_json


class TrialOut(BaseModel):
    id: int
    run_id: int
    persona_id: str
    treatment_idx: int
    repeat_idx: int
    status: str
    attempts: int
    parsed: dict[str, Any] | None
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None


def _trial_out(t: Trial) -> TrialOut:
    return TrialOut(
        id=t.id,
        run_id=t.run_id,
        persona_id=t.persona_id,
        treatment_idx=t.treatment_idx,
        repeat_idx=t.repeat_idx,
        status=t.status,
        attempts=t.attempts,
        parsed=t.parsed_json,
        latency_ms=t.latency_ms,
        prompt_tokens=t.prompt_tokens,
        completion_tokens=t.completion_tokens,
    )


@router.get("/runs/{run_id}/trials")
def list_trials(
    run_id: int, request: Request, status: str | None = None, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with _sessions(request)() as s:
        cond = [Trial.run_id == run_id] + ([Trial.status == status] if status else [])
        total = s.scalar(select(func.count()).select_from(Trial).where(*cond)) or 0
        rows = s.scalars(select(Trial).where(*cond).order_by(Trial.id).offset(offset).limit(limit))
        return {"total": total, "items": [_trial_out(t).model_dump() for t in rows]}


@router.get("/trials/{trial_id}")
def get_trial(trial_id: int, request: Request) -> dict[str, Any]:
    """The full source record behind any number or quote: prompt, raw output, timings."""
    with _sessions(request)() as s:
        t = s.get(Trial, trial_id)
        if t is None:
            raise HTTPException(404, "No such trial")
        return {
            **_trial_out(t).model_dump(),
            "prompt_text": t.prompt_text,
            "raw_output": t.raw_output,
        }


class ReportOut(BaseModel):
    id: int
    run_id: int
    title: str
    created_at: str


@router.post("/runs/{run_id}/reports", status_code=201)
def create_report(run_id: int, request: Request) -> ReportOut:
    with _sessions(request)() as s:
        try:
            computed = build.build_report(s, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        rep = Report(run_id=run_id, title=computed["title"], computed_json=computed)
        s.add(rep)
        s.commit()
        return ReportOut(
            id=rep.id, run_id=run_id, title=rep.title, created_at=computed["generated_at"]
        )


@router.get("/reports")
def list_reports(request: Request) -> list[ReportOut]:
    with _sessions(request)() as s:
        return [
            ReportOut(
                id=r.id, run_id=r.run_id, title=r.title, created_at=r.computed_json["generated_at"]
            )
            for r in s.scalars(select(Report).order_by(Report.id.desc()))
        ]


@router.get("/reports/{report_id}")
def get_report(report_id: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        rep = s.get(Report, report_id)
        if rep is None:
            raise HTTPException(404, "No such report")
        return {"id": rep.id, **rep.computed_json}


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: int, request: Request, format: Literal["md", "html", "json"] = "md"
) -> Response:
    with _sessions(request)() as s:
        rep = s.get(Report, report_id)
        if rep is None:
            raise HTTPException(404, "No such report")
        data = rep.computed_json
    if format == "json":
        body, media = json.dumps(data, indent=2, default=str), "application/json"
    elif format == "html":
        body, media = build.render_html(data), "text/html"
    else:
        body, media = build.render_markdown(data), "text/markdown"
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.{format}"'},
    )
