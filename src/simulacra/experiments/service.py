import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra import __version__
from simulacra.benchmarks.service import TargetSpec, build_target, start_hardware_snapshot
from simulacra.experiments import prompts
from simulacra.experiments.assign import assign_treatment
from simulacra.experiments.handler import KIND
from simulacra.jobs import queue
from simulacra.persistence.models import (
    Experiment,
    PersonaRow,
    PopulationVersion,
    Run,
    Treatment,
)

MAX_TRIALS = 200_000


class Scenario(BaseModel):
    product_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=10, max_length=1500)
    price_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    category: str | None = Field(default=None, max_length=80)
    headline: str | None = Field(default=None, max_length=200)


class TreatmentIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    # Overrides applied on top of the scenario (headline, price_usd, description, ...).
    params: dict[str, Any] = {}


class CreateExperiment(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "product_concept"
    research_question: str = Field(min_length=3, max_length=500)
    hypothesis: str = Field(default="", max_length=500)
    population_version_id: int
    scenario: Scenario
    treatments: list[TreatmentIn] = Field(default_factory=lambda: [TreatmentIn(label="Baseline")])
    design: str = "between"  # between: each persona sees one treatment; within: all of them
    repeats: int = Field(1, ge=1, le=20)
    seed: int = 0


def create_experiment(session: Session, body: CreateExperiment) -> Experiment:
    version = session.get(PopulationVersion, body.population_version_id)
    if version is None or version.status != "ready":
        raise ValueError("choose a population that is ready")
    if body.design not in ("between", "within"):
        raise ValueError("design must be 'between' or 'within'")
    if not 1 <= len(body.treatments) <= 12:
        raise ValueError("an experiment needs between 1 and 12 treatments")
    if len({t.label for t in body.treatments}) != len(body.treatments):
        raise ValueError("treatment labels must be unique")
    exp = Experiment(
        name=body.name,
        kind=body.kind,
        research_question=body.research_question,
        hypothesis=body.hypothesis,
        population_version_id=version.id,
        scenario_json=body.scenario.model_dump(),
        config_json={"design": body.design, "repeats": body.repeats, "seed": body.seed},
    )
    session.add(exp)
    session.flush()
    for i, t in enumerate(body.treatments):
        session.add(Treatment(experiment_id=exp.id, idx=i, label=t.label, params_json=t.params))
    session.commit()
    return exp


class StartOptions(BaseModel):
    target: TargetSpec
    concurrency: int = Field(4, ge=1, le=16)
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(220, ge=32, le=2000)
    batch_size: int = Field(10, ge=1, le=200)
    seed: int | None = None  # defaults to the experiment's seed


def plan_units(
    persona_ids: list[str], n_treatments: int, design: str, repeats: int, seed: int
) -> list[dict[str, Any]]:
    """Deterministic trial plan. Between-subjects assignment is seeded and order independent."""
    units: list[dict[str, Any]] = []
    for pid in persona_ids:
        arms = (
            [assign_treatment(seed, pid, n_treatments)]
            if design == "between"
            else range(n_treatments)
        )
        for t in arms:
            for r in range(repeats):
                units.append(
                    {"idx": len(units), "persona_id": pid, "treatment_idx": t, "repeat_idx": r}
                )
    return units


async def start_run(
    session_factory: Any, experiment_id: int, opts: StartOptions, allow_mock: bool
) -> Run:
    """Freeze the exact configuration into a manifest, create the plan, and queue the run."""
    target = await build_target(opts.target, allow_mock)
    try:
        info = next((m for m in target.model_infos if m.name == opts.target.model), None)
        with session_factory() as s:
            exp = s.get(Experiment, experiment_id)
            if exp is None:
                raise LookupError("no such experiment")
            version = s.get(PopulationVersion, exp.population_version_id)
            if version is None or version.status != "ready":
                raise ValueError("the population is not ready")
            treatments = list(
                s.scalars(
                    select(Treatment)
                    .where(Treatment.experiment_id == exp.id)
                    .order_by(Treatment.idx)
                )
            )
            persona_ids = list(
                s.scalars(
                    select(PersonaRow.synthetic_id)
                    .where(PersonaRow.version_id == version.id)
                    .order_by(PersonaRow.idx)
                )
            )
            seed = opts.seed if opts.seed is not None else int(exp.config_json["seed"])
            units = plan_units(
                persona_ids,
                len(treatments),
                exp.config_json["design"],
                int(exp.config_json["repeats"]),
                seed,
            )
            if len(units) > MAX_TRIALS:
                raise ValueError(f"{len(units)} trials exceeds the limit of {MAX_TRIALS}")
            spec_hash = hashlib.sha256(
                json.dumps(version.spec_json, sort_keys=True).encode()
            ).hexdigest()[:16]
            manifest = {
                "simulacra_version": __version__,
                "experiment": {
                    "id": exp.id,
                    "name": exp.name,
                    "kind": exp.kind,
                    "research_question": exp.research_question,
                    "hypothesis": exp.hypothesis,
                    "scenario": exp.scenario_json,
                    "config": exp.config_json,
                    "treatments": [
                        {"idx": t.idx, "label": t.label, "params": t.params_json}
                        for t in treatments
                    ],
                },
                "population": {
                    "version_id": version.id,
                    "version": version.version,
                    "size": version.size,
                    "seed": version.seed,
                    "source": version.source,
                    "spec_sha256_16": spec_hash,
                },
                "inference": {
                    "runtime": target.runtime.kind.value,
                    "runtime_version": target.runtime.version,
                    "base_url": target.runtime.base_url,
                    "model": opts.target.model,
                    "model_digest": info.digest if info else None,
                    "quantization": info.quantization if info else None,
                    "structured_mode": opts.target.structured_mode,
                    "temperature": opts.temperature,
                    "max_tokens": opts.max_tokens,
                    "concurrency": opts.concurrency,
                    "seed": seed,
                },
                "prompt": {"version": prompts.PROMPT_VERSION, "sha256_12": prompts.prompt_hash()},
                "trials_planned": len(units),
                "hardware": start_hardware_snapshot(),
            }
            config = {
                "experiment_id": exp.id,
                "population_version_id": version.id,
                "target": opts.target.model_dump(),
                "concurrency": opts.concurrency,
                "temperature": opts.temperature,
                "max_tokens": opts.max_tokens,
                "seed": seed,
            }
            return queue.create_run(
                s, KIND, f"{exp.name}", units, config, opts.batch_size, manifest=manifest
            )
    finally:
        await target.backend.aclose()
