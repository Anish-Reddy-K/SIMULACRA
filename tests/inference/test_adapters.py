import json

import httpx
import pytest

from simulacra.inference.ollama import OllamaBackend
from simulacra.inference.openai_compat import OpenAICompatBackend
from simulacra.inference.types import GenerationRequest, Message, RuntimeKind

pytestmark = pytest.mark.anyio

REQ = GenerationRequest(
    model="m", messages=[Message(role="user", content="hi")], json_schema={"type": "object"}, seed=7
)


def client(handler: httpx.MockTransport | None, base: str = "http://x") -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base, transport=handler)


def ndjson(*chunks: dict[str, object]) -> bytes:
    return ("\n".join(json.dumps(c) for c in chunks) + "\n").encode()


async def test_ollama_generate_parses_stream_and_timings() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=ndjson(
                {"message": {"content": '{"a":'}, "done": False},
                {"message": {"content": "1}"}, "done": False},
                {
                    "message": {"content": ""},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 10,
                    "prompt_eval_duration": 20_000_000,
                    "eval_count": 5,
                    "eval_duration": 50_000_000,
                    "load_duration": 3_000_000,
                },
            ),
        )

    backend = OllamaBackend(client=client(httpx.MockTransport(handler)))
    result = await backend.generate(REQ)
    assert result.ok and result.text == '{"a":1}'
    assert (result.prompt_tokens, result.completion_tokens) == (10, 5)
    assert result.decode_tokens_per_s == pytest.approx(100.0)
    assert result.prefill_tokens_per_s == pytest.approx(500.0)
    assert result.load_ms == pytest.approx(3.0)
    assert result.ttft_ms is not None
    assert seen["format"] == {"type": "object"}
    assert seen["options"] == {"temperature": 0.7, "num_predict": 256, "seed": 7}


async def test_ollama_error_responses_do_not_raise() -> None:
    http_500 = OllamaBackend(
        client=client(httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    )
    result = await http_500.generate(REQ)
    assert not result.ok and "500" in (result.error or "")

    in_stream = OllamaBackend(
        client=client(
            httpx.MockTransport(
                lambda r: httpx.Response(200, content=ndjson({"error": "model not found"}))
            )
        )
    )
    assert (await in_stream.generate(REQ)).error == "model not found"


async def test_connection_failure_is_a_failed_result() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    result = await OllamaBackend(client=client(httpx.MockTransport(refuse))).generate(REQ)
    assert not result.ok and "ConnectError" in (result.error or "")


async def test_ollama_lists_models_with_details() -> None:
    payload = {
        "models": [
            {
                "name": "q:3b",
                "digest": "abc",
                "size": 10,
                "details": {"parameter_size": "3B", "quantization_level": "Q4_K_M", "family": "q"},
            }
        ]
    }
    backend = OllamaBackend(
        client=client(httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    )
    [m] = await backend.list_models()
    assert (m.name, m.digest, m.quantization, m.parameter_size) == ("q:3b", "abc", "Q4_K_M", "3B")


def sse(*chunks: dict[str, object]) -> bytes:
    lines = [f"data: {json.dumps(c)}\n" for c in chunks] + ["data: [DONE]\n"]
    return "\n".join(lines).encode()


async def test_openai_compat_generate_uses_usage_and_timings() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "{}"}, "finish_reason": None}]},
                {
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 2},
                    "timings": {"prompt_ms": 30.0, "predicted_ms": 20.0},
                },
            ),
        )

    backend = OpenAICompatBackend(client=client(httpx.MockTransport(handler)))
    result = await backend.generate(REQ)
    assert result.text == "{}" and result.finish_reason == "stop"
    assert (result.prompt_tokens, result.completion_tokens) == (12, 2)
    assert result.decode_tokens_per_s == pytest.approx(100.0)
    assert seen["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert seen["seed"] == 7


async def test_openai_compat_recognises_llama_server_via_props() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        return httpx.Response(
            200,
            json={
                "total_slots": 4,
                "build_info": "b1",
                "default_generation_settings": {"n_ctx": 8192},
            },
        )

    info = await OpenAICompatBackend(client=client(httpx.MockTransport(handler))).info()
    assert info.kind == RuntimeKind.LLAMA_CPP
    assert (info.capabilities.parallel_slots, info.capabilities.context_size) == (4, 8192)


async def test_generic_openai_server_has_unknown_capabilities() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        return httpx.Response(404)

    info = await OpenAICompatBackend(client=client(httpx.MockTransport(handler))).info()
    assert info.kind == RuntimeKind.OPENAI_COMPAT
    assert info.capabilities.json_schema is None  # never claimed without a probe


async def test_prompted_mode_describes_schema_instead_of_constraining() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=sse({"choices": [{"delta": {"content": "{}"}}]}))

    backend = OpenAICompatBackend(client=client(httpx.MockTransport(handler)), constrained=False)
    await backend.generate(REQ)
    assert "response_format" not in seen
    last = seen["messages"][-1]  # type: ignore[index]
    assert last["role"] == "system" and '"type": "object"' in last["content"]
