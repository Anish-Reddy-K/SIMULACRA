import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulacra.api.app import create_app
from simulacra.config import Settings
from simulacra.populations import io as pio


def test_csv_neutralizes_formula_injection() -> None:
    p = {
        "synthetic_id": "P1",
        "name": "=CMD()",
        "attributes": {"age": 30, "note": "-5+3"},
        "bio": "+x",
    }
    out = pio.export_csv([p])
    assert "'=CMD()" in out and "'+x" in out and "'-5+3" in out
    assert ",30," in out  # plain numbers untouched


def test_import_validation() -> None:
    ok = json.dumps({"synthetic_id": "A", "name": "N", "attributes": {"age": 3}, "bio": "b"})
    header, recs = pio.parse_jsonl(
        ('{"_simulacra_population": {"seed": 4}}\n' + ok + "\n").encode()
    )
    assert header["seed"] == 4 and recs[0].synthetic_id == "A"
    with pytest.raises(pio.ImportError_, match="not valid JSON"):
        pio.parse_jsonl(b"{nope")
    with pytest.raises(pio.ImportError_, match="no personas"):
        pio.parse_jsonl(b"\n")
    extra = json.dumps({"synthetic_id": "A", "name": "N", "attributes": {}, "evil": "x"})
    with pytest.raises(pio.ImportError_, match="line 1"):
        pio.parse_jsonl(extra.encode())
    with pytest.raises(pio.ImportError_, match="duplicate"):
        pio.parse_jsonl((ok + "\n" + ok).encode())
    with pytest.raises(pio.ImportError_, match="UTF-8"):
        pio.parse_jsonl(b"\xff\xfe")
    with pytest.raises(pio.ImportError_, match="larger than"):
        pio.parse_jsonl(b"x" * (pio.MAX_IMPORT_BYTES + 1))
    nested = json.dumps({"synthetic_id": "A", "name": "N", "attributes": {"a": {"x": 1}}})
    with pytest.raises(pio.ImportError_):
        pio.parse_jsonl(nested.encode())


@pytest.fixture
def pclient(tmp_path: Path) -> Iterator[TestClient]:
    s = Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "none", enable_mock_backend=True)
    with TestClient(create_app(s), base_url="http://localhost") as c:
        yield c


def spec(client: TestClient, size: int = 50, seed: int = 1) -> dict[str, object]:
    preset = client.get("/api/v1/populations/presets").json()
    return {**preset, "size": size, "seed": seed, "name": "Test pop"}


def test_create_list_detail_personas(pclient: TestClient) -> None:
    r = pclient.post("/api/v1/populations", json={"spec": spec(pclient, 60)})
    assert r.status_code == 201
    v = r.json()
    assert v["status"] == "ready" and v["size"] == 60 and v["version"] == 1
    assert pclient.get("/api/v1/populations").json()[0]["id"] == v["id"]

    d = pclient.get(f"/api/v1/populations/versions/{v['id']}").json()
    assert d["diagnostics"]["size"] == 60 and d["diagnostics"]["marginals"]
    page = pclient.get(f"/api/v1/populations/versions/{v['id']}/personas?limit=20").json()
    assert page["total"] == 60 and len(page["items"]) == 20
    first = page["items"][0]
    assert first["synthetic_id"] == f"P{v['id']}-00001" and first["bio"]
    found = pclient.get(f"/api/v1/populations/versions/{v['id']}/personas?q={first['name']}").json()
    assert found["total"] >= 1
    card = pclient.get(
        f"/api/v1/populations/versions/{v['id']}/personas/{first['synthetic_id']}/card"
    ).json()
    assert first["name"] in card["card"] and card["approx_tokens"] <= 305
    assert (
        pclient.get(f"/api/v1/populations/versions/{v['id']}/personas/nope/card").status_code == 404
    )
    assert pclient.get("/api/v1/populations/versions/9999").status_code == 404


def test_versioning_is_immutable_and_reproducible(pclient: TestClient) -> None:
    a = pclient.post("/api/v1/populations", json={"spec": spec(pclient, 30, 5)}).json()
    b = pclient.post(
        "/api/v1/populations",
        json={"spec": spec(pclient, 30, 5), "population_id": a["population_id"]},
    ).json()
    assert b["population_id"] == a["population_id"] and b["version"] == 2
    pa = pclient.get(f"/api/v1/populations/versions/{a['id']}/personas?limit=200").json()["items"]
    pb = pclient.get(f"/api/v1/populations/versions/{b['id']}/personas?limit=200").json()["items"]
    assert [p["attributes"] for p in pa] == [p["attributes"] for p in pb]  # same seed, same people
    missing = pclient.post(
        "/api/v1/populations", json={"spec": spec(pclient), "population_id": 999}
    )
    assert missing.status_code == 404


def test_invalid_spec_is_rejected(pclient: TestClient) -> None:
    bad = spec(pclient)
    bad["size"] = 0
    assert pclient.post("/api/v1/populations", json={"spec": bad}).status_code == 422
    bad = spec(pclient)
    bad["rules"] = ["nope"]
    assert pclient.post("/api/v1/populations", json={"spec": bad}).status_code == 422


def test_export_then_import_round_trip(pclient: TestClient) -> None:
    v = pclient.post("/api/v1/populations", json={"spec": spec(pclient, 40, 3)}).json()
    jsonl = pclient.get(f"/api/v1/populations/versions/{v['id']}/export?format=jsonl")
    assert jsonl.status_code == 200 and "attachment" in jsonl.headers["content-disposition"]
    csv = pclient.get(f"/api/v1/populations/versions/{v['id']}/export?format=csv").text
    assert csv.splitlines()[0].startswith("synthetic_id,name") and len(csv.splitlines()) == 41

    imp = pclient.post(
        "/api/v1/populations/import?name=Round trip",
        content=jsonl.content,
        headers={"Content-Type": "application/x-ndjson"},
    )
    assert (
        imp.status_code == 201 and imp.json()["size"] == 40 and imp.json()["source"] == "imported"
    )
    orig = pclient.get(f"/api/v1/populations/versions/{v['id']}/personas?limit=200").json()["items"]
    back = pclient.get(
        f"/api/v1/populations/versions/{imp.json()['id']}/personas?limit=200"
    ).json()["items"]
    assert [(p["synthetic_id"], p["attributes"], p["bio"]) for p in orig] == [
        (p["synthetic_id"], p["attributes"], p["bio"]) for p in back
    ]

    bad = pclient.post("/api/v1/populations/import", content=b"not json")
    assert bad.status_code == 422


def test_enrichment_with_mock_backend_completes_and_updates_diagnostics(
    pclient: TestClient,
) -> None:
    import time

    body = {
        "spec": spec(pclient, 12, 2),
        "enrich": {"target": {"base_url": "mock://", "model": "mock-model"}, "concurrency": 2},
    }
    v = pclient.post("/api/v1/populations", json=body).json()
    assert v["status"] == "generating"
    end = time.time() + 30
    while time.time() < end:
        cur = pclient.get(f"/api/v1/populations/versions/{v['id']}").json()
        if cur["version"]["status"] != "generating":
            break
        time.sleep(0.1)
    assert cur["version"]["status"] == "ready"
    assert cur["version"]["progress_done"] == 12
    items = pclient.get(f"/api/v1/populations/versions/{v['id']}/personas?limit=20").json()["items"]
    assert all(p["meta"]["enrichment"] == "llm" for p in items)
    assert pclient.get(f"/api/v1/populations/versions/{v['id']}/export").status_code == 200


def test_enrichment_to_unreachable_runtime_fails_cleanly(pclient: TestClient) -> None:
    import time

    body = {
        "spec": spec(pclient, 5),
        "enrich": {"target": {"base_url": "http://127.0.0.1:9", "model": "x"}},
    }
    v = pclient.post("/api/v1/populations", json=body).json()
    end = time.time() + 20
    while time.time() < end:
        cur = pclient.get(f"/api/v1/populations/versions/{v['id']}").json()["version"]
        if cur["status"] != "generating":
            break
        time.sleep(0.1)
    assert cur["status"] == "failed" and "Could not reach" in cur["error"]
    assert pclient.get(f"/api/v1/populations/versions/{v['id']}/export").status_code == 409


def test_cross_origin_population_writes_rejected(pclient: TestClient) -> None:
    r = pclient.post(
        "/api/v1/populations",
        json={"spec": spec(pclient)},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
