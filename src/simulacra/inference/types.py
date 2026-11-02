from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RuntimeKind(StrEnum):
    OLLAMA = "ollama"
    LLAMA_CPP = "llama.cpp"
    OPENAI_COMPAT = "openai-compat"  # mlx-lm, vllm-mlx, vllm-metal, anything speaking /v1
    MOCK = "mock"


class Message(BaseModel):
    role: str
    content: str


class GenerationRequest(BaseModel):
    """One independent LLM call. Everything that affects the output is explicit and recorded."""

    model: str
    messages: list[Message]
    json_schema: dict[str, Any] | None = None  # constrain decoding server-side when set
    max_tokens: int = 256
    temperature: float = 0.7
    seed: int | None = None
    timeout_s: float = 120.0


class GenerationResult(BaseModel):
    """Output plus the measurements the benchmark and telemetry layers need.

    Timing fields are None when the runtime does not report them: never estimated silently.
    """

    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_ms: float
    ttft_ms: float | None = None  # client-side: request sent -> first content chunk
    prompt_eval_ms: float | None = None  # runtime-reported
    decode_ms: float | None = None  # runtime-reported
    load_ms: float | None = None  # runtime-reported model load (cold start)
    finish_reason: str | None = None
    error: str | None = None  # transport/runtime failure; text is empty when set

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def decode_tokens_per_s(self) -> float | None:
        if self.completion_tokens and self.decode_ms:
            return self.completion_tokens / (self.decode_ms / 1000)
        return None

    @property
    def prefill_tokens_per_s(self) -> float | None:
        if self.prompt_tokens and self.prompt_eval_ms:
            return self.prompt_tokens / (self.prompt_eval_ms / 1000)
        return None


class ModelInfo(BaseModel):
    name: str
    digest: str | None = None
    size_bytes: int | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None


class Capabilities(BaseModel):
    # None means "not known"; only a probe (Phase 4 stage 1) may turn it into a fact.
    json_schema: bool | None = None
    reports_timings: bool = False
    parallel_slots: int | None = None
    context_size: int | None = None


class RuntimeInfo(BaseModel):
    kind: RuntimeKind
    base_url: str
    version: str | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)


class BackendHealth(BaseModel):
    ok: bool
    detail: str | None = None
