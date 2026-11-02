import socket
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from simulacra.api import lab
from simulacra.inference.discovery import Discovery, RuntimeReport, discover
from simulacra.inference.types import ModelInfo, RuntimeInfo, RuntimeKind


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.anyio
async def test_discovery_reports_unreachable_without_raising() -> None:
    dead = free_port()
    found = await discover(ollama_url=f"http://127.0.0.1:{dead}", openai_ports=(free_port(),))
    assert all(not r.running and r.problem == "not_reachable" for r in found.runtimes)
    assert {b.name for b in found.installed} >= {"ollama", "llama.cpp"}


@pytest.fixture
def fake_discovery(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def fake() -> Discovery:
        info = RuntimeInfo(kind=RuntimeKind.OLLAMA, base_url="http://127.0.0.1:11434")
        return Discovery(
            installed=[],
            runtimes=[
                RuntimeReport(
                    base_url=info.base_url, running=True, info=info, models=[ModelInfo(name="m:1b")]
                ),
                RuntimeReport(
                    base_url="http://127.0.0.1:8080", running=False, problem="not_reachable"
                ),
            ],
        )

    monkeypatch.setattr(lab, "discover", fake)
    yield


def test_lab_endpoints(client: TestClient, fake_discovery: None) -> None:
    runtimes = client.get("/api/v1/lab/runtimes").json()
    assert [r["running"] for r in runtimes["runtimes"]] == [True, False]
    models = client.get("/api/v1/lab/models").json()
    assert models == [
        {
            "name": "m:1b",
            "digest": None,
            "size_bytes": None,
            "parameter_size": None,
            "quantization": None,
            "family": None,
            "runtime_base_url": "http://127.0.0.1:11434",
            "runtime_kind": "ollama",
        }
    ]
