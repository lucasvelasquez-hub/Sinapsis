"""Replay de escenarios: eventos en memoria, sin decisiones ni auditoría."""

from app.services.scenario_replay import replay_scenario
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import AuditEvent
from app.models.decision import DispatchDecision
from app.services.benchmarks_service import _load_scenarios_workbook
from app.services.recommendation_service import _traffic_factor, _travel_lookup

AMBULANCES = {"TAM", "TAB"}
FREE_STATES = {"DISPONIBLE", "RETORNANDO"}


def _rows(sheet: str, scenario_id: str) -> list[dict]:
    return [row for row in _load_scenarios_workbook()[sheet] if row["id_escenario"] == scenario_id]


def test_replay_esc12_writes_nothing(db: Session) -> None:
    decisions = db.execute(select(func.count()).select_from(DispatchDecision)).scalar_one()
    audits = db.execute(select(func.count()).select_from(AuditEvent)).scalar_one()
    out = replay_scenario(db, "ESC-12")
    assert db.execute(select(func.count()).select_from(DispatchDecision)).scalar_one() == decisions
    assert db.execute(select(func.count()).select_from(AuditEvent)).scalar_one() == audits
    assert out.events_applied >= 1
    assert any(
        text.startswith("Regla R06:")
        for result in out.results
        for text in (*result.factors, *result.warnings)
    )


def test_replay_esc14_uses_position_after_cancel(db: Session) -> None:
    cancel = next(row for row in _rows("eventos", "ESC-14") if row["tipo_evento"] == "CANCELACION")
    unit_id = str(cancel["id_movil"])
    initial_zone = str(
        next(
            row["id_zona_actual"]
            for row in _rows("estado_inicial_moviles", "ESC-14")
            if row["id_movil"] == unit_id
        )
    )
    post_zone = str(
        next(
            row["id_zona"]
            for row in _rows("solicitudes", "ESC-14")
            if row["id_solicitud"] == cancel["id_solicitud"]
        )
    )
    assert post_zone != initial_zone
    following = max(
        (
            row
            for row in _rows("solicitudes", "ESC-14")
            if row["id_solicitud"] != cancel["id_solicitud"]
            and int(row["minuto_llegada"]) <= int(cancel["minuto"])
        ),
        key=lambda row: int(row["minuto_llegada"]),
    )
    out = replay_scenario(db, "ESC-14")
    result = next(row for row in out.results if row.id_solicitud == following["id_solicitud"])
    assert f"Zona de origen {post_zone}" in result.factors
    assert f"Zona de origen {initial_zone}" not in result.factors


def test_replay_esc04_role_is_first_responder(db: Session) -> None:
    ambulance_ready = any(
        row["tipo_movil"] in AMBULANCES and row["estado"] in FREE_STATES
        for row in _rows("estado_inicial_moviles", "ESC-04")
    )
    out = replay_scenario(db, "ESC-04")
    red = next(row for row in out.results if row.clasificacion_inicial == "01")
    if not ambulance_ready:
        assert red.recommended_role == "PRIMER_RESPONDIENTE_ESTABILIZACION"


def test_replay_esc06_reclass_changes_later_rank(db: Session) -> None:
    event = next(
        row
        for row in _rows("eventos", "ESC-06")
        if row["tipo_evento"] == "RECLASIFICACION_EN_SITIO"
    )
    initial = next(
        row
        for row in _rows("solicitudes", "ESC-06")
        if row["id_solicitud"] == event["id_solicitud"]
    )
    new_code = str(event["nueva_clasificacion"])
    assert new_code != str(initial["clasificacion_inicial"])
    out = replay_scenario(db, "ESC-06")
    result = next(row for row in out.results if row.id_solicitud == event["id_solicitud"])
    assert result.clasificacion_inicial == new_code


def test_replay_esc13_uses_release_minute(db: Session) -> None:
    out = replay_scenario(db, "ESC-13")
    fleet = _rows("estado_inicial_moviles", "ESC-13")
    requests = _rows("solicitudes", "ESC-13")
    start = next(
        row["fecha_hora_inicio"]
        for row in _load_scenarios_workbook()["escenarios"]
        if row["id_escenario"] == "ESC-13"
    )
    from datetime import datetime, timedelta

    start_dt = datetime.strptime(str(start), "%Y-%m-%d %H:%M")
    for req in requests:
        minute = int(req["minuto_llegada"])
        held = {
            str(row["id_movil"])
            for row in fleet
            if row["estado"] == "EN_TRASLADO" and float(row.get("min_para_liberarse") or 0) > minute
        }
        result = next(row for row in out.results if row.id_solicitud == req["id_solicitud"])
        assert result.recommended_unit_id not in held
        if (
            result.recommended_role != "PRIMER_RESPONDIENTE_ESTABILIZACION"
            or result.paired_unit_id is None
        ):
            continue
        when = start_dt + timedelta(minutes=minute)
        traffic = _traffic_factor(db, when)
        zones = {str(row["id_zona_actual"]) for row in fleet}
        travel = _travel_lookup(db, zones, str(req["id_zona"]))
        best_id = None
        best_cost = None
        for row in fleet:
            if row["tipo_movil"] not in AMBULANCES or row["estado"] == "FUERA_SERVICIO":
                continue
            release = float(row.get("min_para_liberarse") or 0)
            if row["estado"] == "EN_ATENCION" and release > minute:
                continue
            if row["estado"] not in FREE_STATES and not (
                row["estado"] == "EN_TRASLADO" or (release > 0 and release <= minute)
            ):
                continue
            valley = travel.get(str(row["id_zona_actual"]))
            if valley is None:
                continue
            remain = (
                max(0.0, release - minute)
                if row["estado"] == "EN_TRASLADO" and release > minute
                else 0.0
            )
            cost = round(round(valley[1] * traffic, 2) + 2.0 + remain, 2)
            uid = str(row["id_movil"])
            if best_cost is None or cost < best_cost or (cost == best_cost and uid < best_id):
                best_cost = cost
                best_id = uid
        assert result.paired_unit_id == best_id
