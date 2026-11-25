"""Tests de los endpoints de escenarios de referencia y KPIs de Grupo EMI."""

from fastapi.testclient import TestClient


def test_kpis_overview_returns_12_kpis_and_baseline(client: TestClient) -> None:
    resp = client.get("/api/v1/benchmarks/kpis")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["kpis"]) == 12
    assert len(body["linea_base"]) == 5
    kpi_01 = next(k for k in body["kpis"] if k["id_kpi"] == "KPI-01")
    assert kpi_01["valor_actual_db"] is not None


def test_scenarios_list_returns_14_scenarios(client: TestClient) -> None:
    resp = client.get("/api/v1/benchmarks/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 14
    assert body[0]["id_escenario"] == "ESC-01"


def test_evaluate_scenario_esc01(client: TestClient) -> None:
    resp = client.post("/api/v1/benchmarks/scenarios/ESC-01/evaluate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"]["id_escenario"] == "ESC-01"
    assert len(body["results"]) == 6
    assert body["type_match_rate"] >= 0.5


def test_evaluate_scenario_esc04_vmd_first_responder(client: TestClient) -> None:
    """En 01 sin ambulancia cercana, la VMD actúa como primer respondiente (R04)."""
    resp = client.post("/api/v1/benchmarks/scenarios/ESC-04/evaluate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"]["id_escenario"] == "ESC-04"
    assert len(body["results"]) >= 1


def test_kpis_separate_observed_and_simulated(client: TestClient) -> None:
    body = client.get("/api/v1/benchmarks/kpis").json()
    kpis = {k["id_kpi"]: k for k in body["kpis"]}
    assert len(kpis) == 12
    assert len(body["linea_base"]) == 5

    assert kpis["KPI-01"]["valor_actual_db"] is not None
    assert kpis["KPI-01"]["valor_simulado"] is not None
    assert kpis["KPI-01"]["procedencia_simulado"] == "SIMULADO"
    assert kpis["KPI-03"]["procedencia_simulado"] == "SIMULADO"

    # KPI-04 mide un reloj humano: solo observado.
    assert kpis["KPI-04"]["valor_actual_db"] is not None
    assert kpis["KPI-04"]["valor_simulado"] is None
    assert kpis["KPI-04"]["procedencia_simulado"] is None

    # KPI-05, 06, 09, 11, 12: solo observados, sobre servicios no sintéticos.
    for kpi_id in ("KPI-05", "KPI-06", "KPI-09", "KPI-11", "KPI-12"):
        assert kpis[kpi_id]["valor_actual_db"] is not None, kpi_id
        assert kpis[kpi_id]["valor_simulado"] is None, kpi_id

    for kpi_id in ("KPI-07", "KPI-08"):
        assert "sugerido" in kpis[kpi_id]["valor_simulado"], kpi_id
        assert "referencia" in kpis[kpi_id]["valor_simulado"], kpi_id
        assert kpis[kpi_id]["procedencia_simulado"] == "SIMULADO"

    assert "%" in kpis["KPI-10"]["valor_simulado"]
    assert kpis["KPI-10"]["procedencia_simulado"] == "SIMULADO"
