from typing import Protocol

from simulacra.inference.types import (
    BackendHealth,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    RuntimeInfo,
)


class InferenceBackend(Protocol):
    """The single interface the rest of Simulacra uses to talk to a local runtime (ADR-0004).

    `generate` never raises for runtime or transport failures; it returns a result with
    `error` set, so callers can count failures instead of crashing a long run.
    """

    async def info(self) -> RuntimeInfo: ...

    async def health(self) -> BackendHealth: ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def aclose(self) -> None: ...
