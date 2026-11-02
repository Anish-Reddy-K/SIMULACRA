"""Integration tests against real local runtimes. Skipped unless SIMULACRA_REAL_INFERENCE=1.

Expected setup (see docs/): Ollama running with qwen2.5:1.5b pulled, and optionally
llama-server on :8080. Tests skip a runtime that is not reachable.
"""

import os
from typing import Literal

import pytest
from pydantic import BaseModel

from simulacra.inference.base import InferenceBackend
from simulacra.inference.discovery import discover
from simulacra.inference.ollama import OllamaBackend
from simulacra.inference.openai_compat import OpenAICompatBackend
from simulacra.inference.structured import generate_structured
from simulacra.inference.types import GenerationRequest, Message, RuntimeKind

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("SIMULACRA_REAL_INFERENCE") != "1", reason="set SIMULACRA_REAL_INFERENCE=1"
    ),
]

OLLAMA_MODEL = os.environ.get("SIMULACRA_TEST_OLLAMA_MODEL", "qwen2.5:1.5b")


class Verdict(BaseModel):
    answer: Literal["yes", "no"]
    reason: str


REQUEST = GenerationRequest(
    model=OLLAMA_MODEL,
    messages=[
        Message(role="system", content="Answer with JSON only."),
        Message(role="user", content="Is the sky blue on a clear day? Give answer and reason."),
    ],
    temperature=0.0,
    seed=1,
    max_tokens=80,
)


async def backends() -> list[tuple[str, InferenceBackend, str]]:
    found = await discover()
    out: list[tuple[str, InferenceBackend, str]] = []
    for r in found.runtimes:
        if not (r.running and r.info and r.models):
            continue
        if r.info.kind == RuntimeKind.OLLAMA:
            out.append(("ollama", OllamaBackend(r.base_url), OLLAMA_MODEL))
        else:
            out.append((r.info.kind.value, OpenAICompatBackend(r.base_url), r.models[0].name))
    return out


async def test_discovery_finds_a_runtime_with_models() -> None:
    assert await backends(), "no running runtime with models found"


async def test_real_structured_generation_on_every_running_runtime() -> None:
    for name, backend, model in await backends():
        req = REQUEST.model_copy(update={"model": model})
        outcome = await generate_structured(backend, req, Verdict)
        gen = outcome.generation
        assert gen.ok, f"{name}: {gen.error}"
        assert outcome.valid, f"{name}: {outcome.status} {outcome.detail} text={gen.text!r}"
        assert outcome.parsed is not None and outcome.parsed.answer == "yes"
        assert gen.completion_tokens and gen.completion_tokens > 0
        assert gen.ttft_ms is not None and gen.ttft_ms < gen.total_ms
        assert gen.decode_tokens_per_s and gen.decode_tokens_per_s > 0, f"{name}: no timings"
        await backend.aclose()


async def test_unknown_model_is_a_failed_result_not_an_exception() -> None:
    backend = OllamaBackend()
    req = REQUEST.model_copy(update={"model": "does-not-exist:1b"})
    result = await backend.generate(req)
    assert not result.ok and result.error
    await backend.aclose()
