import asyncio
import shutil
from typing import Literal

import httpx
from pydantic import BaseModel

from simulacra.inference.ollama import OllamaBackend
from simulacra.inference.openai_compat import OpenAICompatBackend
from simulacra.inference.types import ModelInfo, RuntimeInfo

# Conventional ports. Binaries are looked up on PATH; nothing is ever installed or started.
BINARIES = {
    "ollama": "ollama",
    "llama.cpp": "llama-server",
    "mlx-lm": "mlx_lm.server",
    "vllm-mlx": "vllm-mlx",
}
OPENAI_COMPAT_PORTS = (8080, 8000, 1234)
OLLAMA_URL = "http://127.0.0.1:11434"


class InstalledBinary(BaseModel):
    name: str
    path: str | None


class RuntimeReport(BaseModel):
    """A running runtime, its models, or the reason it was not reachable."""

    base_url: str
    running: bool
    info: RuntimeInfo | None = None
    models: list[ModelInfo] = []
    problem: Literal["not_reachable", "error"] | None = None


class Discovery(BaseModel):
    installed: list[InstalledBinary]
    runtimes: list[RuntimeReport]


async def _probe(base_url: str, kind: Literal["ollama", "openai"]) -> RuntimeReport:
    client = httpx.AsyncClient(base_url=base_url)
    backend = (
        OllamaBackend(base_url, client)
        if kind == "ollama"
        else OpenAICompatBackend(base_url, client)
    )
    try:
        info = await backend.info()
        models = await backend.list_models()
        return RuntimeReport(base_url=base_url, running=True, info=info, models=models)
    except httpx.ConnectError:
        return RuntimeReport(base_url=base_url, running=False, problem="not_reachable")
    except (httpx.HTTPError, ValueError, KeyError):
        return RuntimeReport(base_url=base_url, running=False, problem="error")
    finally:
        await backend.aclose()


async def discover(
    ollama_url: str = OLLAMA_URL,
    openai_ports: tuple[int, ...] = OPENAI_COMPAT_PORTS,
    extra_urls: tuple[str, ...] = (),
) -> Discovery:
    """Find installed runtime binaries and which servers are answering right now."""
    installed = [InstalledBinary(name=n, path=shutil.which(b)) for n, b in BINARIES.items()]
    probes = [_probe(ollama_url, "ollama")]
    urls = [f"http://127.0.0.1:{p}" for p in openai_ports] + list(extra_urls)
    probes += [_probe(u, "openai") for u in urls]
    return Discovery(installed=installed, runtimes=list(await asyncio.gather(*probes)))
