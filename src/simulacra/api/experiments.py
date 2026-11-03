import csv
import io
import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from simulacra.analysis import compare as compare_mod
from simulacra.analysis import concept, explore, runcompare, synthesis, themes
from simulacra.experiments import service as svc
from simulacra.experiments import templates
from simulacra.persistence.models import Experiment, Report, Run, RunEvent, Treatment, Trial
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


@router.get("/runs/{run_id}/comparison")
def comparison(run_id: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        try:
            return compare_mod.compare(s, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/experiment-templates")
def experiment_templates() -> list[dict[str, Any]]:
    return templates.TEMPLATES


class FromTemplate(BaseModel):
    template: Literal["product_concept", "ad_comparison", "pricing"]
    name: str
    research_question: str
    hypothesis: str = ""
    population_version_id: int
    scenario: svc.Scenario
    headlines: list[str] = []
    prices: list[float] = []
    repeats: int = 1
    seed: int = 0
    design: Literal["between", "within"] = "between"


@router.post("/experiments/from-template", status_code=201)
def from_template(body: FromTemplate, request: Request) -> ExperimentOut:
    try:
        if body.template == "ad_comparison":
            arms = templates.ad_comparison(body.headlines)
        elif body.template == "pricing":
            arms = templates.pricing(body.prices)
        else:
            arms = [svc.TreatmentIn(label="Baseline")]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    full = svc.CreateExperiment(
        name=body.name,
        kind=body.template,
        research_question=body.research_question,
        hypothesis=body.hypothesis,
        population_version_id=body.population_version_id,
        scenario=body.scenario,
        treatments=arms,
        design=body.design,
        repeats=body.repeats,
        seed=body.seed,
    )
    return create_experiment(full, request)


@router.post("/experiments/{experiment_id}/clone", status_code=201)
def clone_experiment(experiment_id: int, request: Request) -> ExperimentOut:
    """Reuse an experiment's exact design (treatments, scenario, config) as a new experiment."""
    with _sessions(request)() as s:
        exp = s.get(Experiment, experiment_id)
        if exp is None:
            raise HTTPException(404, "No such experiment")
        arms = [
            svc.TreatmentIn(label=t.label, params=t.params_json)
            for t in s.scalars(
                select(Treatment).where(Treatment.experiment_id == exp.id).order_by(Treatment.idx)
            )
        ]
        body = svc.CreateExperiment(
            name=f"{exp.name} (copy)",
            kind=exp.kind,
            research_question=exp.research_question,
            hypothesis=exp.hypothesis,
            population_version_id=exp.population_version_id,
            scenario=svc.Scenario(**exp.scenario_json),
            treatments=arms,
            design=exp.config_json["design"],
            repeats=exp.config_json["repeats"],
            seed=exp.config_json["seed"],
        )
        new = svc.create_experiment(s, body)
        return _exp_out(s, new)


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
    run_id: int,
    request: Request,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
    intent: str | None = None,
    objection: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with _sessions(request)() as s:
        cond = [Trial.run_id == run_id] + ([Trial.status == status] if status else [])
        if intent:
            cond.append(Trial.parsed_json["purchase_intent"].as_string() == intent)
        if objection:
            cond.append(Trial.parsed_json["top_objection"].as_string() == objection)
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


@router.get("/runs/{run_id}/performance")
def performance(run_id: int, request: Request) -> dict[str, Any]:
    """Measured performance of a run, computed from stored trials (nothing is estimated)."""
    settings = request.app.state.settings
    with _sessions(request)() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "No such run")
        rows = s.execute(
            select(
                Trial.status,
                Trial.attempts,
                Trial.latency_ms,
                Trial.prompt_tokens,
                Trial.completion_tokens,
                Trial.created_at,
            ).where(Trial.run_id == run_id)
        ).all()
        retries = (
            s.scalar(
                select(func.count())
                .select_from(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.kind == "retry")
            )
            or 0
        )
        resource_events = (
            s.scalar(
                select(func.count())
                .select_from(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.kind == "resource")
            )
            or 0
        )
    n = len(rows)
    valid = sum(1 for r in rows if r.status == "valid")
    lat = sorted(r.latency_ms for r in rows)
    started = run.started_at.timestamp() if run.started_at else None
    finished = run.finished_at.timestamp() if run.finished_at else None
    if started is not None and run.started_at is not None and run.started_at.tzinfo is None:
        started = run.started_at.replace(tzinfo=__import__("datetime").UTC).timestamp()
    if finished is not None and run.finished_at is not None and run.finished_at.tzinfo is None:
        finished = run.finished_at.replace(tzinfo=__import__("datetime").UTC).timestamp()
    wall = (finished - started) if started is not None and finished is not None else None
    windows: dict[int, int] = {}
    for r in rows:
        windows[int(r.created_at // 300)] = windows.get(int(r.created_at // 300), 0) + 1
    ordered = [windows[k] for k in sorted(windows)]
    db_file = settings.data_dir / "simulacra.db"
    comp = sum(r.completion_tokens or 0 for r in rows)
    prompt = sum(r.prompt_tokens or 0 for r in rows)
    return {
        "run_id": run_id,
        "state": run.state,
        "trials": n,
        "valid": valid,
        "wall_s": wall,
        "valid_per_min": valid / (wall / 60) if wall else None,
        "prompt_tokens": prompt,
        "completion_tokens": comp,
        "completion_tokens_per_s": comp / wall if wall else None,
        "prompt_tokens_mean": prompt / n if n else None,
        "completion_tokens_mean": comp / n if n else None,
        "latency_ms_median": lat[len(lat) // 2] if lat else None,
        "latency_ms_p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None,
        "trials_with_retry_attempt": sum(1 for r in rows if r.attempts > 1),
        "failure_rate": sum(1 for r in rows if r.status == "request_failed") / n if n else None,
        "invalid_rate": sum(1 for r in rows if r.status in ("invalid_json", "schema_mismatch")) / n
        if n
        else None,
        "batch_retries": retries,
        "resource_events": resource_events,
        "throughput_per_5min_window": ordered,
        "database_mb": db_file.stat().st_size / 2**20 if db_file.exists() else None,
    }


@router.get("/runs/{run_id}/synthesis")
def get_synthesis(run_id: int, request: Request) -> dict[str, Any]:
    """Key findings as claims with numbers and evidence trial ids, plus an independent verification."""
    with _sessions(request)() as s:
        try:
            claims = synthesis.build(s, run_id)
            return {"claims": claims, "verification": synthesis.verify(s, run_id, claims)}
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/runs/{run_id}/themes")
def get_themes(run_id: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        try:
            _run, trials, _personas, _labels = concept.load(s, run_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        valid = [t for t in trials if t.status == "valid" and t.parsed_json]
        groups: dict[str, list[str]] = {}
        for t in valid:
            code = concept.parsed(t)["top_objection"]
            if code != "none":
                groups.setdefault(code, []).append(concept.parsed(t)["reason"])
        clusters = themes.cluster_reasons([(t.id, concept.parsed(t)["reason"]) for t in valid])
    return {
        "by_objection": themes.distinctive_terms(groups),
        "clusters": [
            {
                "size": c.size,
                "exemplar_trial_id": c.exemplar_trial_id,
                "exemplar_text": c.exemplar_text,
                "terms": c.terms,
                "trial_ids": c.trial_ids[:10],
            }
            for c in clusters
        ],
        "note": "Words are ranked by weighted log-odds against the other objections; clusters group reasons "
        "with similar wording. Both are computed from the stored text, with no model involved.",
    }


@router.get("/runs/{run_id}/query")
def query_run(
    run_id: int,
    request: Request,
    metric: str,
    group_by: str | None = None,
    treatment: int | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    """Structured question: filters are passed as filter_<attribute>=<value> query parameters."""
    filters = {
        k[len("filter_") :]: v for k, v in request.query_params.items() if k.startswith("filter_")
    }
    with _sessions(request)() as s:
        try:
            return explore.query(
                s, run_id, metric, group_by or None, treatment, filters or None, code
            )
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except explore.QueryError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.get("/compare-runs")
def compare_two_runs(a: int, b: int, request: Request) -> dict[str, Any]:
    with _sessions(request)() as s:
        try:
            return runcompare.compare_runs(s, a, b)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc


def _safe_cell(value: Any) -> str:
    """Neutralize spreadsheet formula injection in exported text."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/runs/{run_id}/export/trials.csv")
def export_trials_csv(run_id: int, request: Request) -> Response:
    with _sessions(request)() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "No such run")
        trials = list(s.scalars(select(Trial).where(Trial.run_id == run_id).order_by(Trial.id)))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            "trial_id",
            "persona_id",
            "treatment_idx",
            "repeat_idx",
            "status",
            "purchase_intent",
            "appeal",
            "top_benefit",
            "top_objection",
            "reason",
            "prompt_tokens",
            "completion_tokens",
            "latency_ms",
        ]
    )
    for t in trials:
        p = t.parsed_json or {}
        w.writerow(
            [t.id, t.persona_id, t.treatment_idx, t.repeat_idx, t.status]
            + [
                _safe_cell(p.get(k, ""))
                for k in ("purchase_intent", "appeal", "top_benefit", "top_objection", "reason")
            ]
            + [t.prompt_tokens, t.completion_tokens, round(t.latency_ms, 1)]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="trials-{run_id}.csv"'},
    )
