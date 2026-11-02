import pytest

from simulacra.config import Settings


def test_defaults_bind_localhost_only() -> None:
    assert Settings().host == "127.0.0.1"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULACRA_PORT", "9999")
    assert Settings().port == 9999
