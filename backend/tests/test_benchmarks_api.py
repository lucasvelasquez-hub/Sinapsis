"""Tests de API para endpoints consolidados de benchmarks y KPIs EMI (Task 4)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_evaluate_all_scenarios_returns_14_summaries_and_totals(client: TestClient) -> None:
    res = client.post("/api/v1/benchmarks/scenarios/evaluate-all")
    assert res.status_code == 200
    body = res.json()

    assert body["provenance"] == "SIMULADO"
    assert len(body["scenarios"]) == 14

    totals = body["totals"]
    assert totals["total_scenarios"] == 14
    assert totals["total_requests"] == 58
    assert 0.0 <= totals["type_match_rate"] <= 1.0
    assert 0.0 <= totals["unit_match_rate"] <= 1.0
    assert totals["avg_eta_core_min"] is not None
    assert totals["avg_eta_ref_min"] is not None
    assert totals["eta_delta_min"] is not None
    assert 0.0 <= totals["sla_core_pct"] <= 100.0
    assert 0.0 <= totals["sla_ref_pct"] <= 100.0
    assert sum(totals["discrepancy_counts"].values()) == 58
    assert totals["r01_incompatible_count"] == 0
    assert totals["r03_vital_without_ambulance_or_pair"] == 0


def test_kpis_overview_preserves_observed_vs_simulated_boundary(client: TestClient) -> None:
    res = client.get("/api/v1/benchmarks/kpis")
    assert res.status_code == 200
    body = res.json()
    by_id = {k["id_kpi"]: k for k in body["kpis"]}
    assert len(by_id) == 12
    for kpi_id in ("KPI-01", "KPI-02", "KPI-03", "KPI-07", "KPI-08", "KPI-10"):
        assert by_id[kpi_id]["valor_simulado"] is not None, f"Falta valor_simulado en {kpi_id}"
        assert by_id[kpi_id]["procedencia_simulado"] == "SIMULADO"
    for kpi_id in ("KPI-04", "KPI-05", "KPI-06", "KPI-09", "KPI-11", "KPI-12"):
        assert by_id[kpi_id]["valor_actual_db"] is not None
        assert by_id[kpi_id]["valor_simulado"] is None
