from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CORE API"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"
    assert data["status"] == "ok"
