import asyncio
import json
from collections.abc import Callable
from typing import Any

from simulacra.inference.types import (
    BackendHealth,
    Capabilities,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    RuntimeInfo,
    RuntimeKind,
)

Responder = Callable[[GenerationRequest], str]


def _default_responder(request: GenerationRequest) -> str:
    return json.dumps({"ok": True})


class MockBackend:
    """Deterministic in-process backend for CI, tests and demos. Never used silently."""

    def __init__(
        self,
        responder: Responder = _default_responder,
        latency_s: float = 0.0,
        fail_every: int = 0,
        models: list[str] | None = None,
    ) -> None:
        self.responder = responder
        self.latency_s = latency_s
        self.fail_every = fail_every
        self.calls = 0
        self._models = models or ["mock-model"]

    async def info(self) -> RuntimeInfo:
        return RuntimeInfo(
            kind=RuntimeKind.MOCK,
            base_url="mock://",
            version="1",
            capabilities=Capabilities(json_schema=True, reports_timings=True, parallel_slots=64),
        )

    async def health(self) -> BackendHealth:
        return BackendHealth(ok=True)

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=n) for n in self._models]

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls += 1
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        if self.fail_every and self.calls % self.fail_every == 0:
            return GenerationResult(total_ms=self.latency_s * 1000, error="mock failure")
        text = self.responder(request)
        tokens = max(1, len(text) // 4)
        ms = self.latency_s * 1000
        extra: dict[str, Any] = {"decode_ms": max(ms, 1.0), "prompt_eval_ms": 1.0}
        return GenerationResult(
            text=text,
            prompt_tokens=sum(len(m.content) for m in request.messages) // 4,
            completion_tokens=tokens,
            total_ms=ms,
            ttft_ms=ms,
            finish_reason="stop",
            **extra,
        )

    async def aclose(self) -> None:
        return None
