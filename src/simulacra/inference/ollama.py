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

NS_PER_MS = 1_000_000


class OllamaBackend:
    """Ollama native API. Streams so time-to-first-token can be measured."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self.base_url)

    async def info(self) -> RuntimeInfo:
        resp = await self._client.get("/api/version", timeout=3)
        resp.raise_for_status()
        return RuntimeInfo(
            kind=RuntimeKind.OLLAMA,
            base_url=self.base_url,
            version=resp.json().get("version"),
            capabilities=Capabilities(json_schema=True, reports_timings=True),
        )

    async def health(self) -> BackendHealth:
        try:
            await self.info()
        except httpx.HTTPError as exc:
            return BackendHealth(ok=False, detail=f"{type(exc).__name__}: {exc}")
        return BackendHealth(ok=True)

    async def list_models(self) -> list[ModelInfo]:
        resp = await self._client.get("/api/tags", timeout=5)
        resp.raise_for_status()
        models = []
        for m in resp.json().get("models", []):
            d = m.get("details", {})
            models.append(
                ModelInfo(
                    name=m["name"],
                    digest=m.get("digest"),
                    size_bytes=m.get("size"),
                    parameter_size=d.get("parameter_size"),
                    quantization=d.get("quantization_level"),
                    family=d.get("family"),
                )
            )
        return models

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        if request.seed is not None:
            options["seed"] = request.seed
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": True,
            "options": options,
        }
        if request.json_schema is not None:
            body["format"] = request.json_schema

        start = time.perf_counter()
        ttft_ms: float | None = None
        parts: list[str] = []
        final: dict[str, Any] = {}
        try:
            async with self._client.stream(
                "POST", "/api/chat", json=body, timeout=request.timeout_s
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:300]
                    return _failure(start, f"HTTP {resp.status_code}: {detail}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        return _failure(start, str(chunk["error"]))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - start) * 1000
                        parts.append(content)
                    if chunk.get("done"):
                        final = chunk
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            return _failure(start, f"{type(exc).__name__}: {exc}")

        return GenerationResult(
            text="".join(parts),
            prompt_tokens=final.get("prompt_eval_count"),
            completion_tokens=final.get("eval_count"),
            total_ms=(time.perf_counter() - start) * 1000,
            ttft_ms=ttft_ms,
            prompt_eval_ms=_ms(final.get("prompt_eval_duration")),
            decode_ms=_ms(final.get("eval_duration")),
            load_ms=_ms(final.get("load_duration")),
            finish_reason=final.get("done_reason"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _ms(ns: int | None) -> float | None:
    return ns / NS_PER_MS if ns is not None else None


def _failure(start: float, error: str) -> GenerationResult:
    return GenerationResult(total_ms=(time.perf_counter() - start) * 1000, error=error)
