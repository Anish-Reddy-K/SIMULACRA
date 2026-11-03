from fastapi.testclient import TestClient


def test_health_reports_ok_with_wal(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {"ok": True, "journal_mode": "wal"}
    assert body["worker"]["status"] == "not_running"


def test_non_local_host_header_rejected(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"Host": "evil.example.com"})
    assert resp.status_code == 400


def test_127_host_allowed(client: TestClient) -> None:
    assert client.get("/api/v1/health", headers={"Host": "127.0.0.1:8765"}).status_code == 200


def test_web_ui_served_and_api_not_shadowed(client: TestClient) -> None:
    assert "Simulacra" in client.get("/").text
    assert client.get("/api/v1/nope").status_code == 404
