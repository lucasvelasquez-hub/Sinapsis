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
    assert comp_body["released_unit_id"] is None

    held = client.get("/api/v1/simulation/state").json()
    held_unit = next(u for u in held["units"] if u["unit_id"] == top_unit)
    assert held_unit["simulated_available"] is False

    released = client.post(f"/api/v1/simulation/release/{sid}")
    assert released.status_code == 200
    assert released.json()["released_unit_id"] == top_unit

    free = client.get("/api/v1/simulation/state").json()
    clinic_zone = next(c["zone_id"] for c in free["care_centers"] if c["center_id"] == "CLI-01")
    free_unit = next(u for u in free["units"] if u["unit_id"] == top_unit)
    assert free_unit["simulated_available"] is True
    assert free_unit["current_zone_id"] == clinic_zone


def test_cancel_en_route_keeps_current_zone(client: TestClient) -> None:
    state = client.get("/api/v1/simulation/state").json()
    bases = {b["base_id"]: b["zone_id"] for b in state["bases"]}
    service_zone = "Z-SAB-01"
    unit = next(
        u
        for u in state["units"]
        if u["simulated_available"]
        and u["current_zone_id"] != service_zone
        and bases[u["base_id"]] != service_zone
    )
    created = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "03",
            "service_type": "Dolor torácico",
            "zone_id": service_zone,
            "request_datetime": "2026-05-01T13:00:00",
        },
    )
    assert created.status_code == 201, created.text
    sid = created.json()["service_id"]
    rec = client.post("/api/v1/recommendations/evaluate", json={"service_id": sid})
    assert rec.status_code == 200, rec.text
    dec = client.post(
        "/api/v1/decisions",
        json={
            "service_id": sid,
            "recommendation_id": rec.json()["recommendation_id"],
            "recommended_unit_id": rec.json()["candidates"][0]["unit_id"],
            "assigned_unit_id": unit["unit_id"],
            "accepted": True,
            "dispatcher_id": "desp-01",
        },
    )
    assert dec.status_code == 201, dec.text

    base_zone = bases[unit["base_id"]]
    base = next(b for b in state["bases"] if b["base_id"] == unit["base_id"])
    parked = client.post(
        "/api/v1/simulation/positions",
        json={
            "positions": [
                {
                    "unit_id": unit["unit_id"],
                    "lat": base["lat"],
                    "lon": base["lon"],
                    "zone_id": base_zone,
                }
            ]
        },
    )
    assert parked.status_code == 200, parked.text

    comp = client.post(
        f"/api/v1/simulation/complete/{sid}",
        json={"closure_state": "CANCELADO_POR_USUARIO"},
    )
    assert comp.status_code == 200, comp.text
    assert comp.json()["released_unit_id"] == unit["unit_id"]

    after = client.get("/api/v1/simulation/state").json()
    moved = next(u for u in after["units"] if u["unit_id"] == unit["unit_id"])
    assert moved["current_zone_id"] == service_zone
    assert moved["current_zone_id"] != bases[unit["base_id"]]
    assert moved["simulated_available"] is True
