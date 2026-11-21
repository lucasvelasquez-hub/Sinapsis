"""Tests de simulación en vivo: telemetría lat/lon, llegada, traslado, reloj y cierre."""

from fastapi.testclient import TestClient


def test_simulation_state_positions_arrive_advance_and_complete(client: TestClient) -> None:
    state_resp = client.get("/api/v1/simulation/state")
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert len(state["zones"]) == 62
    assert len(state["bases"]) == 8
    assert len(state["care_centers"]) == 10
    assert len(state["units"]) == 26

    # Enviar nueva posición lat/lon para MOV-001 (Sabaneta)
    pos_resp = client.post(
        "/api/v1/simulation/positions",
        json={"positions": [{"unit_id": "MOV-001", "lat": 6.151, "lon": -75.614}]},
    )
    assert pos_resp.status_code == 200
    assert pos_resp.json()["updated"] == 1

    # Avanzar reloj simulado +15 min
    adv = client.post("/api/v1/simulation/advance-clock", json={"minutes": 15})
    assert adv.status_code == 200
    assert adv.json()["traffic_factor"] >= 1.0

    # Crear solicitud sintética, evaluar y despachar
    sim_req = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "01",
            "service_type": "Dolor torácico",
            "zone_id": "Z-SAB-01",
            "request_datetime": "2026-05-01T12:00:00",
        },
    )
    assert sim_req.status_code == 201
    sid = sim_req.json()["service_id"]

    rec = client.post("/api/v1/recommendations/evaluate", json={"service_id": sid}).json()
    assert rec["status"] == "GENERATED"
    top_unit = rec["candidates"][0]["unit_id"]

    dec = client.post(
        "/api/v1/decisions",
        json={
            "service_id": sid,
            "recommendation_id": rec["recommendation_id"],
            "recommended_unit_id": top_unit,
            "assigned_unit_id": top_unit,
            "accepted": True,
            "dispatcher_id": "desp-01",
        },
    )
    assert dec.status_code == 201

    # Registrar llegada al paciente
    arr = client.post(f"/api/v1/simulation/arrive/{sid}")
    assert arr.status_code == 200
    assert arr.json()["arrival_datetime"] is not None

    # Completar con traslado a CLI-01 y liberar la móvil en zona de la clínica
    comp = client.post(
        f"/api/v1/simulation/complete/{sid}",
        json={"closure_state": "TRASLADADO", "destination_center_id": "CLI-01"},
    )
    assert comp.status_code == 200
    comp_body = comp.json()
    assert comp_body["status"] == "COMPLETED"
    assert comp_body["closure_state"] == "TRASLADADO"
    assert comp_body["destination_center"] is not None
    assert comp_body["released_unit_id"] == top_unit
