from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CORE API"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"
    assert data["status"] == "ok"
