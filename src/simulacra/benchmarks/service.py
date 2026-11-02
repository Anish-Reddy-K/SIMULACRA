import asyncio
import json
import time
from collections.abc import Callable
from typing import Any, Literal

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from simulacra.benchmarks import repository as repo
from simulacra.benchmarks.hardware import detect_hardware
from simulacra.benchmarks.runner import Stage, Target, run_target
from simulacra.inference.mock import MockBackend
from simulacra.inference.ollama import OllamaBackend
from simulacra.inference.openai_compat import OpenAICompatBackend
from simulacra.inference.types import GenerationRequest, RuntimeInfo, RuntimeKind

MOCK_URL = "mock://"


class TargetSpec(BaseModel):
    base_url: str
    model: str
    structured_mode: Literal["constrained", "prompted"] = "constrained"


def _example(schema: dict[str, Any], defs: dict[str, Any] | None = None) -> Any:
    """Deterministic schema-valid value (used only by the mock backend)."""
    defs = defs or schema.get("$defs", {})
    if "$ref" in schema:
        return _example(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][-1] if "pass" in schema["enum"] else schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        return {k: _example(v, defs) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return []
    if kind == "integer":
        return schema.get("minimum", 1)
    if kind == "boolean":
        return True
    return "ok"


def mock_responder(request: GenerationRequest) -> str:
    return json.dumps(_example(request.json_schema or {"type": "object"}))


async def build_target(spec: TargetSpec, allow_mock: bool = False) -> Target:
    """Connect to a runtime and describe it. Raises ValueError with a user-facing message."""
    if spec.base_url == MOCK_URL:
        if not allow_mock:
            raise ValueError("The mock backend is disabled.")
        mock = MockBackend(mock_responder, latency_s=0.01, models=[spec.model])
        return Target(
            f"mock / {spec.model}",
            mock,
            spec.model,
            await mock.info(),
            spec.structured_mode,
            model_infos=await mock.list_models(),
        )
    base = spec.base_url.rstrip("/")
    last: Exception | None = None
    for backend_cls in (OllamaBackend, OpenAICompatBackend):
        client = httpx.AsyncClient(base_url=base)
        try:
            if backend_cls is OpenAICompatBackend:
                backend: OllamaBackend | OpenAICompatBackend = OpenAICompatBackend(
                    base, client, constrained=spec.structured_mode == "constrained"
                )
            else:
                backend = OllamaBackend(base, client)
            info: RuntimeInfo = await backend.info()
            models = await backend.list_models()
            if info.kind != RuntimeKind.OLLAMA and spec.base_url.endswith("11434"):
                continue
            return Target(
                f"{info.kind.value} / {spec.model}",
                backend,
                spec.model,
                info,
                spec.structured_mode,
                model_infos=models,
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            last = exc
            await client.aclose()
    raise ValueError(f"Could not reach a runtime at {spec.base_url} ({type(last).__name__}).")


class Progress:
    """Throttled progress writer so the database is not hammered per trial."""

    def __init__(self, session_factory: Callable[[], Session], run_id: int) -> None:
        self.session_factory, self.run_id, self._last = session_factory, run_id, 0.0

    async def __call__(self, op: str, done: int, total: int) -> None:
        now = time.monotonic()
        if done < total and now - self._last < 0.4:
            return
        self._last = now
        with self.session_factory() as session:
            repo.update_progress(session, self.run_id, op, done, total)


async def execute_run(
    session_factory: Callable[[], Session],
    run_id: int,
    stage: Stage,
    specs: list[TargetSpec],
    soak_seconds: float = 300.0,
    allow_mock: bool = False,
) -> None:
    """Run a benchmark to completion, persisting results as each target finishes."""

    def event(message: str) -> None:
        with session_factory() as s:
            repo.add_event(s, run_id, message)

    progress = Progress(session_factory, run_id)
    failures = 0
    try:
        for spec in specs:
            try:
                target = await build_target(spec, allow_mock)
            except ValueError as exc:
                failures += 1
                event(f"Skipped {spec.model} at {spec.base_url}: {exc}")
                continue
            event(f"Starting {stage} benchmark of {target.label} ({target.runtime.kind.value})")
            try:
                report = await run_target(target, stage, progress, soak_seconds)
            finally:
                await target.backend.aclose()
            with session_factory() as s:
                repo.save_records(s, run_id, target, report.records)
            if report.skipped_reason:
                failures += 1
                event(f"{target.label}: {report.skipped_reason}")
            else:
                event(f"Finished {target.label}")
        status = "completed" if failures == 0 else "completed_with_errors"
        if failures == len(specs):
            status = "failed"
        with session_factory() as s:
            repo.set_status(s, run_id, status)
        event(f"Benchmark {status}")
    except asyncio.CancelledError:
        with session_factory() as s:
            repo.set_status(s, run_id, "cancelled")
        event("Benchmark cancelled")
        raise
    except Exception as exc:
        with session_factory() as s:
            repo.set_status(s, run_id, "failed", f"{type(exc).__name__}: {exc}")
        event(f"Benchmark failed: {type(exc).__name__}: {exc}")


def start_hardware_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = json.loads(detect_hardware().model_dump_json())
    return snapshot
