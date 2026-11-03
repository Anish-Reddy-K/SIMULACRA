import asyncio
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from simulacra.benchmarks.service import TargetSpec, build_target
from simulacra.experiments import prompts
from simulacra.experiments.assign import trial_seed
from simulacra.experiments.schemas import ConceptReaction
from simulacra.inference.retry import generate_with_retry
from simulacra.inference.structured import validate_output
from simulacra.inference.types import GenerationRequest
from simulacra.jobs.handlers import BatchContext, UnitResult
from simulacra.persistence.models import Experiment, PersonaRow, Treatment, Trial
from simulacra.populations.context import build_card
from simulacra.populations.service import persona_dict

KIND = "experiment"
TRANSPORT_RETRIES = 2
INVALID_RETRIES = 1  # one fresh attempt for invalid model output; the failure is still counted


class ExperimentHandler:
    """Runs one batch of trials: persona x treatment x repeat, one independent LLM call each."""

    kind = KIND

    def __init__(self, session_factory: Callable[[], Session], allow_mock: bool = False) -> None:
        self.session_factory = session_factory
        self.allow_mock = allow_mock
        self._targets: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def _target(self, spec: dict[str, Any]) -> Any:
        key = f"{spec['base_url']}|{spec['model']}|{spec.get('structured_mode', 'constrained')}"
        async with self._lock:
            if key not in self._targets:
                self._targets[key] = await build_target(TargetSpec(**spec), self.allow_mock)
            return self._targets[key]

    async def process(self, ctx: BatchContext) -> list[UnitResult]:
        cfg = ctx.claimed.config
        units = ctx.units
        with self.session_factory() as s:
            exp = s.get(Experiment, int(cfg["experiment_id"]))
            if exp is None:
                raise RuntimeError("experiment no longer exists")
            scenario = dict(exp.scenario_json)
            treatments = {
                t.idx: dict(t.params_json)
                for t in s.scalars(select(Treatment).where(Treatment.experiment_id == exp.id))
            }
            wanted = sorted({u["persona_id"] for u in units})
            rows = s.scalars(
                select(PersonaRow).where(
                    PersonaRow.version_id == int(cfg["population_version_id"]),
                    PersonaRow.synthetic_id.in_(wanted),
                )
            )
            personas = {r.synthetic_id: persona_dict(r) for r in rows}
        missing = [p for p in wanted if p not in personas]
        if missing:
            raise RuntimeError(f"personas missing from the population: {missing[:3]}")

        target = await self._target(cfg["target"])
        sem = asyncio.Semaphore(int(cfg.get("concurrency", 4)))
        out: list[UnitResult] = []
        trial_rows: list[dict[str, Any]] = []

        async def one(unit: dict[str, Any]) -> None:
            persona = personas[unit["persona_id"]]
            t_idx, r_idx = int(unit["treatment_idx"]), int(unit["repeat_idx"])
            messages = prompts.build_messages(
                scenario,
                treatments[t_idx],
                build_card(persona, max_tokens=int(cfg.get("card_tokens", 300))),
            )
            base_seed = trial_seed(int(cfg["seed"]), persona["synthetic_id"], t_idx, r_idx)
            status, attempts, text, parsed, gen = "request_failed", 0, "", None, None
            async with sem:
                for attempt in range(1 + INVALID_RETRIES):
                    attempts = attempt + 1
                    req = GenerationRequest(
                        model=target.model,
                        messages=messages,
                        json_schema=ConceptReaction.model_json_schema(),
                        max_tokens=int(cfg.get("max_tokens", 220)),
                        temperature=float(cfg.get("temperature", 0.7)),
                        seed=base_seed + attempt,
                        timeout_s=float(cfg.get("timeout_s", 120)),
                    )
                    gen, _ = await generate_with_retry(target.backend, req, TRANSPORT_RETRIES)
                    if not gen.ok:
                        status, text = "request_failed", gen.error or ""
                        break
                    text = gen.text
                    status, model_obj, _detail = validate_output(text, ConceptReaction)
                    if status == "valid" and model_obj is not None:
                        parsed = model_obj.model_dump()
                        break
            assert gen is not None  # noqa: S101  (loop runs at least once)
            trial_rows.append(
                {
                    "persona_id": persona["synthetic_id"],
                    "treatment_idx": t_idx,
                    "repeat_idx": r_idx,
                    "status": status,
                    "attempts": attempts,
                    "prompt_text": prompts.flatten(messages),
                    "raw_output": text[:4000],
                    "parsed_json": parsed,
                    "prompt_tokens": gen.prompt_tokens,
                    "completion_tokens": gen.completion_tokens,
                    "latency_ms": gen.total_ms,
                }
            )
            out.append(
                (int(unit["idx"]), "ok" if status == "valid" else "error", {"status": status})
            )

        await asyncio.gather(*(one(u) for u in units))
        run_id = ctx.claimed.run_id

        def write_trials(session: Session) -> None:
            now = time.time()
            session.execute(
                sqlite_insert(Trial)
                .values([{**r, "run_id": run_id, "created_at": now} for r in trial_rows])
                .on_conflict_do_nothing(
                    index_elements=["run_id", "persona_id", "treatment_idx", "repeat_idx"]
                )
            )

        ctx.hooks.append(write_trials)
        return sorted(out)
