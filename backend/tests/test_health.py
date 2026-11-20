from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CORE API"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"
    assert data["status"] == "ok"


def test_check_db_connection_logs_failure(monkeypatch, caplog) -> None:
    from app.core import database

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(database.engine, "connect", boom)

    assert database.check_db_connection() is False
    assert any("db down" in (r.exc_text or "") or r.exc_info for r in caplog.records)


def test_cors_allows_frontend_dev_ports(client: TestClient) -> None:
    for origin in ("http://localhost:3000", "http://localhost:3011"):
        resp = client.options(
            "/api/v1/requests",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

        assert resp.status_code == 200, origin
        assert resp.headers.get("access-control-allow-origin") == origin
