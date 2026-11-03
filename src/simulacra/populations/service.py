import asyncio
from collections.abc import Callable
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra.benchmarks.service import TargetSpec, build_target
from simulacra.persistence.models import PersonaRow, Population, PopulationVersion
from simulacra.populations import diagnostics as diag
from simulacra.populations.bio import FIRST_NAMES, template_bio
from simulacra.populations.enrich import enrich_all
from simulacra.populations.io import PersonaRecord
from simulacra.populations.sampler import SampleResult, sample_population
from simulacra.populations.spec import PopulationSpec


def persona_dict(row: PersonaRow) -> dict[str, Any]:
    return {
        "synthetic_id": row.synthetic_id,
        "name": row.name,
        "attributes": row.attributes_json,
        "bio": row.bio,
        "interests": row.extras_json.get("interests", []),
        "brand_attitudes": row.extras_json.get("brand_attitudes", ""),
        "quirk": row.extras_json.get("quirk", ""),
        "meta": row.meta_json,
    }


def _build(spec: PopulationSpec, version_id: int) -> tuple[list[dict[str, Any]], SampleResult]:
    sample = sample_population(spec)
    rng = np.random.default_rng(spec.seed + 1)  # separate stream: names never alter sampling
    personas = []
    for i, attrs in enumerate(sample.personas):
        name = FIRST_NAMES[int(rng.integers(len(FIRST_NAMES)))]
        full = {"name": name, **attrs}
        personas.append(
            {
                "synthetic_id": f"P{version_id}-{i + 1:05d}",
                "name": name,
                "attributes": attrs,
                "bio": template_bio(full),
                "interests": [],
                "brand_attitudes": "",
                "quirk": "",
                "meta": {"enrichment": "template"},
            }
        )
    return personas, sample


def _as_row_fields(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "synthetic_id": p["synthetic_id"],
        "name": p["name"],
        "attributes_json": p["attributes"],
        "bio": p["bio"],
        "meta_json": p["meta"],
        "extras_json": {k: p[k] for k in ("interests", "brand_attitudes", "quirk")},
    }


def create_generated(
    session: Session,
    spec: PopulationSpec,
    population_id: int | None,
    enrichment: dict[str, Any] | None,
) -> PopulationVersion:
    if population_id is None:
        pop = Population(name=spec.name)
        session.add(pop)
        session.flush()
    else:
        found = session.get(Population, population_id)
        if found is None:
            raise LookupError("no such population")
        pop = found
    latest = session.scalar(
        select(PopulationVersion.version)
        .where(PopulationVersion.population_id == pop.id)
        .order_by(PopulationVersion.version.desc())
        .limit(1)
    )
    version = PopulationVersion(
        population_id=pop.id,
        version=(latest or 0) + 1,
        status="generating",
        source="generated",
        spec_json=spec.model_dump(mode="json"),
        seed=spec.seed,
        size=spec.size,
        enrichment_json=enrichment or {},
        progress_total=spec.size if enrichment else 0,
    )
    session.add(version)
    session.flush()
    personas, sample = _build(spec, version.id)
    session.add_all(
        PersonaRow(version_id=version.id, idx=i, **_as_row_fields(p))
        for i, p in enumerate(personas)
    )
    version.diagnostics_json = diag.compute(spec, sample, personas).model_dump(mode="json")
    version.status = "generating" if enrichment else "ready"
    session.commit()
    return version


def create_imported(
    session: Session, name: str, header: dict[str, Any], records: list[PersonaRecord]
) -> PopulationVersion:
    pop = Population(name=name)
    session.add(pop)
    session.flush()
    version = PopulationVersion(
        population_id=pop.id,
        version=1,
        status="ready",
        source="imported",
        spec_json=header,
        seed=int(header.get("seed", 0))
        if str(header.get("seed", "0")).lstrip("-").isdigit()
        else 0,
        size=len(records),
        enrichment_json={},
        diagnostics_json=None,
    )
    session.add(version)
    session.flush()
    for i, r in enumerate(records):
        session.add(
            PersonaRow(
                version_id=version.id,
                idx=i,
                synthetic_id=r.synthetic_id,
                name=r.name,
                attributes_json=dict(r.attributes),
                bio=r.bio,
                extras_json={
                    "interests": r.interests,
                    "brand_attitudes": r.brand_attitudes,
                    "quirk": r.quirk,
                },
                meta_json={"enrichment": "imported"},
            )
        )
    session.commit()
    return version


async def run_enrichment(
    session_factory: Callable[[], Session],
    version_id: int,
    target_spec: TargetSpec,
    concurrency: int,
    allow_mock: bool,
) -> None:
    """Replace template bios with LLM-written ones, then recompute diagnostics and finalize."""

    def fail(message: str) -> None:
        with session_factory() as s:
            v = s.get(PopulationVersion, version_id)
            if v is not None:
                v.status, v.error = "failed", message
                s.commit()

    try:
        target = await build_target(target_spec, allow_mock)
    except ValueError as exc:
        fail(str(exc))
        return
    try:
        with session_factory() as s:
            v = s.get(PopulationVersion, version_id)
            if v is None:
                return
            spec = PopulationSpec.model_validate(v.spec_json)
            rows = list(
                s.scalars(
                    select(PersonaRow)
                    .where(PersonaRow.version_id == version_id)
                    .order_by(PersonaRow.idx)
                )
            )
            persona_inputs = [{"name": r.name, **r.attributes_json} for r in rows]
        last = 0.0

        async def progress(done: int, total: int) -> None:
            nonlocal last
            now = asyncio.get_running_loop().time()
            if done < total and now - last < 1.0:
                return
            last = now
            with session_factory() as s2:
                v2 = s2.get(PopulationVersion, version_id)
                if v2 is not None:
                    v2.progress_done, v2.progress_total = done, total
                    s2.commit()

        results = await enrich_all(
            target.backend, target.model, persona_inputs, spec.seed, concurrency, progress
        )
        with session_factory() as s:
            v = s.get(PopulationVersion, version_id)
            if v is None:
                return
            rows = list(
                s.scalars(
                    select(PersonaRow)
                    .where(PersonaRow.version_id == version_id)
                    .order_by(PersonaRow.idx)
                )
            )
            for row, res in zip(rows, results, strict=True):
                row.bio = res["bio"]
                row.extras_json = {k: res[k] for k in ("interests", "brand_attitudes", "quirk")}
                row.meta_json = res["meta"]
            s.flush()
            personas = [persona_dict(r) for r in rows]
            sample = SampleResult(personas=[p["attributes"] for p in personas])
            old = v.diagnostics_json or {}
            d = diag.compute(spec, sample, personas)
            d.rule_rejections = old.get("rule_rejections", {})
            d.unsatisfied_rules = old.get("unsatisfied_rules", 0)
            v.diagnostics_json = d.model_dump(mode="json")
            v.status = "ready"
            v.progress_done = v.progress_total
            s.commit()
    except asyncio.CancelledError:
        fail("cancelled")
        raise
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
    finally:
        await target.backend.aclose()


def mark_interrupted(session: Session) -> int:
    stuck = session.scalars(
        select(PopulationVersion).where(PopulationVersion.status == "generating")
    ).all()
    for v in stuck:
        v.status, v.error = "failed", "interrupted: the server stopped while this was generating"
    session.commit()
    return len(stuck)
