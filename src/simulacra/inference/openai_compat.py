import json
import time
from typing import Any

import httpx

from simulacra.inference.types import (
    BackendHealth,
    Capabilities,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    RuntimeInfo,
    RuntimeKind,
)


class OpenAICompatBackend:
    """Any server speaking /v1/chat/completions: llama-server, mlx-lm, vllm-mlx, vllm-metal.

    llama-server is recognised via /props so its slot count, context size and per-request
    timings can be used. Everything else is treated as a generic server with unknown
    capabilities until probed.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        constrained: bool = True,
    ) -> None:
        # constrained=False is for servers that ignore response_format (e.g. mlx_lm.server):
        # the schema is described in the prompt instead. Output is still strictly validated.
        self.constrained = constrained
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.AsyncClient(base_url=self.base_url, headers=headers)

    async def info(self) -> RuntimeInfo:
        models = await self._client.get("/v1/models", timeout=3)
        models.raise_for_status()
        props = await self._props()
        if props is None:
            return RuntimeInfo(kind=RuntimeKind.OPENAI_COMPAT, base_url=self.base_url)
        settings = props.get("default_generation_settings", {})
        return RuntimeInfo(
            kind=RuntimeKind.LLAMA_CPP,
            base_url=self.base_url,
            version=props.get("build_info"),
            capabilities=Capabilities(
                json_schema=True,
                reports_timings=True,
                parallel_slots=props.get("total_slots"),
                context_size=settings.get("n_ctx"),
            ),
        )

    async def _props(self) -> dict[str, Any] | None:
        try:
            resp = await self._client.get("/props", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, dict) and "total_slots" in data else None
        except (httpx.HTTPError, ValueError):
            pass
        return None

    async def health(self) -> BackendHealth:
        try:
            resp = await self._client.get("/v1/models", timeout=3)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return BackendHealth(ok=False, detail=f"{type(exc).__name__}: {exc}")
        return BackendHealth(ok=True)

    async def list_models(self) -> list[ModelInfo]:
        resp = await self._client.get("/v1/models", timeout=5)
        resp.raise_for_status()
        return [ModelInfo(name=m["id"]) for m in resp.json().get("data", [])]

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        messages = [m.model_dump() for m in request.messages]
        if request.json_schema is not None and not self.constrained:
            messages.append(
                {
                    "role": "system",
                    "content": "Respond with a single JSON object, no other text, matching this "
                    f"JSON schema: {json.dumps(request.json_schema)}",
                }
            )
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.seed is not None:
            body["seed"] = request.seed
        if request.json_schema is not None and self.constrained:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": request.json_schema},
            }

        start = time.perf_counter()
        ttft_ms: float | None = None
        parts: list[str] = []
        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        finish: str | None = None
        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=body, timeout=request.timeout_s
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:300]
                    return _failure(start, f"HTTP {resp.status_code}: {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    if "error" in chunk:
                        return _failure(start, str(chunk["error"]))
                    usage = chunk.get("usage") or usage
                    timings = chunk.get("timings") or timings
                    for choice in chunk.get("choices", []):
                        content = (choice.get("delta") or {}).get("content")
                        if content:
                            if ttft_ms is None:
                                ttft_ms = (time.perf_counter() - start) * 1000
                            parts.append(content)
                        finish = choice.get("finish_reason") or finish
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            return _failure(start, f"{type(exc).__name__}: {exc}")

        return GenerationResult(
            text="".join(parts),
            prompt_tokens=usage.get("prompt_tokens", timings.get("prompt_n")),
            completion_tokens=usage.get("completion_tokens", timings.get("predicted_n")),
            total_ms=(time.perf_counter() - start) * 1000,
            ttft_ms=ttft_ms,
            prompt_eval_ms=timings.get("prompt_ms"),
            decode_ms=timings.get("predicted_ms"),
            finish_reason=finish,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _failure(start: float, error: str) -> GenerationResult:
    return GenerationResult(total_ms=(time.perf_counter() - start) * 1000, error=error)
