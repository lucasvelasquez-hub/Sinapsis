from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_dispatch_recommendation_decision_flow() -> None:
    # 1. Overview & Demand
    ov = client.get("/api/v1/analytics/overview")
    assert ov.status_code == 200
    assert ov.json()["total_services"] >= 10000

    dem = client.get("/api/v1/analytics/demand")
    assert dem.status_code == 200
    assert len(dem.json()["by_zone"]) == 8

    # 2. Fleet units
    fleet = client.get("/api/v1/fleet/units")
    assert fleet.status_code == 200
    assert len(fleet.json()) == 30

    # 3. Create synthetic request
    sim_resp = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "CRITICAL",
            "service_type": "MEDICAL_CRITICAL",
            "zone_id": "ZONE-01",
            "request_datetime": "2026-10-30T10:00:00",
        },
    )
    assert sim_resp.status_code == 201
    sim_data = sim_resp.json()
    service_id = sim_data["service_id"]
    assert sim_data["status"] == "PENDING"
    assert sim_data["context"]["target_response_min"] == 8

    # 4. Eligibility check
    elig_resp = client.get(f"/api/v1/fleet/eligibility/{service_id}")
    assert elig_resp.status_code == 200
    elig_data = elig_resp.json()
    assert len(elig_data["eligible_units"]) > 0
    assert len(elig_data["excluded_units"]) > 0

    # 5. Evaluate MCDM recommendations
    rec_resp = client.post(
        "/api/v1/recommendations/evaluate",
        json={"service_id": service_id},
    )
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["status"] == "GENERATED"
    assert 1 <= len(rec_data["candidates"]) <= 3
    top = rec_data["candidates"][0]
    assert top["rank"] == 1
    assert len(top["factors"]) > 0
    assert len(top["warnings"]) > 0

    # 6. Fetch recommendation by id
    rec_get = client.get(f"/api/v1/recommendations/{rec_data['recommendation_id']}")
    assert rec_get.status_code == 200

    # 7. Record human decision accepting top recommendation
    dec_resp = client.post(
        "/api/v1/decisions",
        json={
            "service_id": service_id,
            "recommendation_id": rec_data["recommendation_id"],
            "recommended_unit_id": top["unit_id"],
            "assigned_unit_id": top["unit_id"],
            "recommendation_score": top["score"],
            "accepted": True,
        },
    )
    assert dec_resp.status_code == 201
    assert dec_resp.json()["assigned_unit_id"] == top["unit_id"]

    # 8. Verify unit is now excluded in a subsequent request at 10:10:00
    sim_resp_2 = client.post(
        "/api/v1/requests/simulate",
        json={
            "urgency_level": "HIGH",
            "service_type": "MEDICAL_CRITICAL",
            "zone_id": "ZONE-01",
            "request_datetime": "2026-10-30T10:10:00",
        },
    )
    assert sim_resp_2.status_code == 201
    elig_2 = client.get(f"/api/v1/fleet/eligibility/{sim_resp_2.json()['service_id']}").json()
    excluded_ids = {u["unit_id"]: u["reasons"] for u in elig_2["excluded_units"]}
    assert top["unit_id"] in excluded_ids
    assert any("BUSY_IN_SIMULATION" in r for r in excluded_ids[top["unit_id"]])
