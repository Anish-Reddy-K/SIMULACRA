import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from simulacra.jobs.queue import Claimed

UnitResult = tuple[int, str, dict[str, Any]]  # (unit idx, "ok" | "error", payload)


@dataclass
class BatchContext:
    claimed: Claimed
    lease_lost: asyncio.Event  # set by the worker when its lease can no longer be extended
    # Handlers append callables that write their own rows inside the commit transaction.
    hooks: list[Callable[[Session], None]] = field(default_factory=list)

    @property
    def units(self) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = self.claimed.payload["units"]
        return units


class Handler(Protocol):
    kind: str

    async def process(self, ctx: BatchContext) -> list[UnitResult]: ...


class DemoHandler:
    """Deterministic handler for tests and demos. Config knobs inject failures.

    sleep_s: per-unit delay. error_units: unit indexes reported as errors.
    fail_batches: {"<batch_idx>": n} raises on the first n attempts of that batch.
    """

    kind = "demo"

    async def process(self, ctx: BatchContext) -> list[UnitResult]:
        cfg = ctx.claimed.config
        fails = int(cfg.get("fail_batches", {}).get(str(ctx.claimed.batch_idx), 0))
        if ctx.claimed.attempts <= fails:
            raise RuntimeError(f"injected failure in batch {ctx.claimed.batch_idx}")
        out: list[UnitResult] = []
        for unit in ctx.units:
            if ctx.lease_lost.is_set():
                raise RuntimeError("lease lost")
            await asyncio.sleep(float(cfg.get("sleep_s", 0.0)))
            idx = int(unit["idx"])
            if idx in cfg.get("error_units", []):
                out.append((idx, "error", {"error": "injected unit error"}))
            else:
                out.append((idx, "ok", {"value": idx * 2}))
        return out


def default_registry(
    enable_demo: bool, session_factory: Callable[[], Session]
) -> dict[str, Handler]:
    from simulacra.experiments.handler import ExperimentHandler

    registry: dict[str, Handler] = {"experiment": ExperimentHandler(session_factory, enable_demo)}
    if enable_demo:
        registry["demo"] = DemoHandler()
    return registry
