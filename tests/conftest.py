from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulacra.api.app import create_app
from simulacra.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>Simulacra</h1>")
    return Settings(data_dir=tmp_path / "data", web_dir=web)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), base_url="http://localhost") as c:
        yield c
