"""Flujo mensual SIMULADO generado desde el histórico (scripts/generate_monthly_flow.py)."""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schemas.dispatch import SimulateRequestCreate

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from generate_monthly_flow import day_class, generate_flow  # noqa: E402

API_FIELDS = set(SimulateRequestCreate.model_fields)


@pytest.fixture(scope="module")
def november() -> dict:
    return generate_flow(2026, 11, seed=42)


def test_same_seed_same_flow_and_other_seed_differs(november: dict) -> None:
    again = generate_flow(2026, 11, seed=42)
    assert again["solicitudes"] == november["solicitudes"]
    assert generate_flow(2026, 11, seed=7)["solicitudes"] != november["solicitudes"]


def test_requests_are_in_month_sorted_and_uniquely_identified(november: dict) -> None:
    reqs = november["solicitudes"]
    stamps = [datetime.fromisoformat(r["request_datetime"]) for r in reqs]
    assert all((t.year, t.month) == (2026, 11) for t in stamps)
    assert stamps == sorted(stamps)
    assert [r["id_flujo"] for r in reqs] == [f"FLU-202611-{i:05d}" for i in range(1, len(reqs) + 1)]
    assert (
        november["total_solicitudes"] == len(reqs) == sum(d["generadas"] for d in november["dias"])
    )
    assert len(november["dias"]) == 30


def test_every_request_is_strict_json_and_valid_for_the_simulate_endpoint(november: dict) -> None:
    json.dumps(november, allow_nan=False)  # sin NaN (canal nulo en el histórico)
    for r in november["solicitudes"]:
        SimulateRequestCreate(**{k: v for k, v in r.items() if k in API_FIELDS})


def test_november_holidays_use_sunday_level(november: dict) -> None:
    assert november["festivos_del_mes"] == ["2026-11-02", "2026-11-16"]
    assert day_class(date(2026, 11, 2)) == day_class(date(2026, 11, 1)) == 6  # festivo = domingo
    by_day = {d["fecha"]: d for d in november["dias"]}
    assert by_day["2026-11-02"]["festivo"] is True
    assert by_day["2026-11-02"]["esperadas"] == by_day["2026-11-01"]["esperadas"]  # domingo
    assert by_day["2026-11-09"]["esperadas"] > by_day["2026-11-02"]["esperadas"]  # lunes normal


def test_flow_resembles_history(november: dict) -> None:
    v = november["validacion"]
    assert abs(v["media_dia_generado"] - v["media_dia_historico"]) / v["media_dia_historico"] < 0.1
    assert v["urgencia_max_dif_pp"] < 3
    assert v["hora_max_dif_pp"] < 1.5
    assert v["zona_variacion_total_pp"] < 10


def test_only_2026_has_a_holiday_calendar() -> None:
    with pytest.raises(ValueError, match="festivos"):
        generate_flow(2027, 1)


def test_generated_requests_are_accepted_by_the_simulate_endpoint(
    client: TestClient, november: dict
) -> None:
    """Extremo a extremo: el endpoint acepta el flujo tal cual (transacción revertida)."""
    for r in november["solicitudes"][:3]:
        payload = {k: v for k, v in r.items() if k in API_FIELDS}
        resp = client.post("/api/v1/requests/simulate", json=payload)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["zone_id"] == r["zone_id"]
        assert body["urgency_level"] == r["urgency_level"]
