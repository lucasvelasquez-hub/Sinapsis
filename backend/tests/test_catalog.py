"""Catálogo de valores del dataset y validación de solicitudes simuladas contra él."""

from fastapi.testclient import TestClient

VALID = {"urgency_level": "ALTA", "service_type": "EMERGENCIA_MEDICA", "zone_id": "COMUNA_01"}


def test_catalog_lists_dataset_values(client: TestClient) -> None:
    resp = client.get("/api/v1/catalog")

    assert resp.status_code == 200
    body = resp.json()
    assert [u["code"] for u in body["urgencies"]] == ["CRITICA", "ALTA", "MEDIA", "BAJA"]
    assert body["urgencies"][0]["target_response_min"] == 8
    assert len(body["zones"]) == 16
    assert body["zones"][0] == "COMUNA_01"
    assert "EVENTO_ESPECIAL" in body["service_types"]
    assert body["unit_types"] == ["AVANZADA", "BASICA", "MEDICALIZADA"]
    assert body["shifts"] == ["TURNO_24H", "TURNO_DIA", "TURNO_NOCHE"]


def test_simulate_rejects_unknown_zone(client: TestClient) -> None:
    resp = client.post("/api/v1/requests/simulate", json=VALID | {"zone_id": "ZONE-01"})

    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "ZONE-01" in error["message"]


def test_simulate_rejects_unknown_service_type(client: TestClient) -> None:
    resp = client.post("/api/v1/requests/simulate", json=VALID | {"service_type": "MEDICAL_URGENT"})

    assert resp.status_code == 422
    assert "MEDICAL_URGENT" in resp.json()["error"]["message"]


def test_simulate_rejects_unknown_urgency(client: TestClient) -> None:
    resp = client.post("/api/v1/requests/simulate", json=VALID | {"urgency_level": "HIGH"})

    assert resp.status_code == 422


def test_simulated_request_detail_uses_new_fields(client: TestClient) -> None:
    resp = client.post("/api/v1/requests/simulate", json=VALID)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["context"]["target_response_min"] == 15
    assert "sla_label" not in body["context"]
    assert body["arrival_datetime"] is None and body["closure_datetime"] is None
    assert "completion_datetime" not in body
