"""Recorre un escenario en memoria. No escribe decisiones ni auditoría."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.domain.assignment_policy import r06_factor
from app.models.raw import RawService, RawServiceRule, RawUnit
from app.schemas.benchmarks import (
    ScenarioEvaluationOut,
    ScenarioRequestEvalOut,
)
from app.schemas.dispatch import EligibilityEvaluation, ExclusionReason, UnitStatusOut
from app.services.benchmarks_service import _load_scenarios_workbook, list_scenarios
from app.services.recommendation_service import score_candidates
from app.services.scoring_service import get_scoring_config

FREE_STATES = {"DISPONIBLE", "RETORNANDO"}
DIVERTABLE_CODES = {"03", "06"}
VITAL_CODES = {"01", "02"}


@dataclass
class _Unit:
    unit_id: str
    unit_type: str
    base_id: str
    state: str
    zone_id: str
    release_at: float
    diversion_of: str | None = None


def replay_scenario(db: Session, scenario_id: str) -> ScenarioEvaluationOut:
    scenarios = {item.id_escenario: item for item in list_scenarios()}
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise ResourceNotFoundError("Scenario", scenario_id)

    data = _load_scenarios_workbook()
    fleet = {
        str(row["id_movil"]): _Unit(
            unit_id=str(row["id_movil"]),
            unit_type=str(row["tipo_movil"]),
            base_id=str(row["id_base"]),
            state=str(row["estado"]),
            zone_id=str(row["id_zona_actual"]),
            release_at=float(row.get("min_para_liberarse") or 0),
        )
        for row in data["estado_inicial_moviles"]
        if row["id_escenario"] == scenario_id
    }
    requests = [row for row in data["solicitudes"] if row["id_escenario"] == scenario_id]
    events = [row for row in data["eventos"] if row["id_escenario"] == scenario_id]
    by_request = {str(row["id_solicitud"]): row for row in requests}
    codes = {str(row["id_solicitud"]): str(row["clasificacion_inicial"]) for row in requests}
    ref_decisions = {
        row["id_solicitud"]: row
        for row in data["decision_despachador"]
        if row["id_escenario"] == scenario_id and int(row.get("orden_movil") or 1) == 1
    }
    units_db = {unit.unit_id: unit for unit in db.execute(select(RawUnit)).scalars().all()}
    rules_by_urg: dict[str, dict[str, int]] = {}
    for rule in db.execute(
        select(RawServiceRule).where(RawServiceRule.eligible.is_(True))
    ).scalars():
        rules_by_urg.setdefault(rule.urgency_level, {})[rule.unit_type] = rule.compatibility_rank
    config = get_scoring_config(db)
    start_dt = datetime.strptime(scenario.fecha_hora_inicio, "%Y-%m-%d %H:%M")

    timeline: list[tuple[int, int, str, Any]] = []
    for req in requests:
        timeline.append((int(req["minuto_llegada"]), 1, "req", req))
    for event in events:
        timeline.append((int(event["minuto"]), 0, "event", event))
    timeline.sort(key=lambda item: (item[0], item[1]))

    results: dict[str, ScenarioRequestEvalOut] = {}
    order: list[str] = []
    cancelled: set[str] = set()

    def remember(result: ScenarioRequestEvalOut) -> None:
        if result.id_solicitud not in results:
            order.append(result.id_solicitud)
        results[result.id_solicitud] = result

    def rank(req: dict[str, Any], minute: int) -> None:
        req_id = str(req["id_solicitud"])
        remember(
            _rank_request(
                db,
                req,
                codes[req_id],
                minute,
                start_dt,
                fleet,
                by_request,
                codes,
                rules_by_urg,
                units_db,
                config,
                ref_decisions.get(req_id, {}),
            )
        )

    for _minute, _order, kind, item in timeline:
        if kind == "req":
            rank(item, int(item["minuto_llegada"]))
            continue
        _apply_event(item, fleet, by_request, codes, cancelled)
        if item["tipo_evento"] in ("RECLASIFICACION_EN_SITIO", "RECLASIFICACION_TELEFONICA"):
            target = by_request.get(str(item["id_solicitud"]))
            if target is not None:
                rank(target, int(item["minuto"]))
        elif item["tipo_evento"] == "CANCELACION":
            for req in requests:
                req_id = str(req["id_solicitud"])
                if req_id in cancelled:
                    continue
                if int(req["minuto_llegada"]) > int(item["minuto"]):
                    continue
                if int(req["minuto_llegada"]) < int(
                    by_request[str(item["id_solicitud"])]["minuto_llegada"]
                ):
                    continue
                rank(req, int(item["minuto"]))
        elif item["tipo_evento"] == "REASIGNACION":
            urgent = _urgent_open(requests, codes, cancelled, int(item["minuto"]))
            unit = fleet.get(str(item["id_movil"]))
            origin_id = str(item["id_solicitud"])
            if urgent is not None and unit is not None and codes.get(origin_id) in DIVERTABLE_CODES:
                origin = by_request[origin_id]
                unit.zone_id = str(origin["id_zona"])
                unit.state = "DISPONIBLE"
                unit.diversion_of = origin_id
                rank(urgent, int(item["minuto"]))
                unit.state = "EN_RUTA"
                unit.diversion_of = None

    total = len(order) or 1
    unit_matches = sum(1 for req_id in order if results[req_id].matches_reference_unit)
    type_matches = sum(1 for req_id in order if results[req_id].matches_reference_type)
    return ScenarioEvaluationOut(
        scenario=scenario,
        results=[results[req_id] for req_id in order],
        unit_match_rate=round(unit_matches / total, 4),
        type_match_rate=round(type_matches / total, 4),
        events_applied=len(events),
    )


def _urgent_open(
    requests: list[dict[str, Any]],
    codes: dict[str, str],
    cancelled: set[str],
    minute: int,
) -> dict[str, Any] | None:
    open_rows = [
        row
        for row in requests
        if str(row["id_solicitud"]) not in cancelled
        and codes[str(row["id_solicitud"])] in VITAL_CODES
        and int(row["minuto_llegada"]) <= minute
    ]
    if not open_rows:
        return None
    return max(open_rows, key=lambda row: int(row["minuto_llegada"]))


def _apply_event(
    event: dict[str, Any],
    fleet: dict[str, _Unit],
    requests: dict[str, dict[str, Any]],
    codes: dict[str, str],
    cancelled: set[str],
) -> None:
    kind = str(event["tipo_evento"])
    unit = fleet.get(str(event.get("id_movil") or ""))
    req_id = str(event.get("id_solicitud") or "")
    if kind == "MOVIL_LIBERADA" and unit is not None:
        unit.state = "DISPONIBLE"
        unit.release_at = 0
        unit.diversion_of = None
    elif kind == "CANCELACION":
        cancelled.add(req_id)
        origin = requests.get(req_id)
        if unit is not None and origin is not None:
            unit.state = "DISPONIBLE"
            unit.zone_id = str(origin["id_zona"])
            unit.release_at = 0
            unit.diversion_of = None
    elif kind in ("RECLASIFICACION_EN_SITIO", "RECLASIFICACION_TELEFONICA"):
        new_code = event.get("nueva_clasificacion")
        if new_code and req_id in codes:
            codes[req_id] = str(new_code)


def _rank_request(
    db: Session,
    req: dict[str, Any],
    urgency: str,
    minute: int,
    start_dt: datetime,
    fleet: dict[str, _Unit],
    requests: dict[str, dict[str, Any]],
    codes: dict[str, str],
    rules_by_urg: dict[str, dict[str, int]],
    units_db: dict[str, RawUnit],
    config: Any,
    ref: dict[str, Any],
) -> ScenarioRequestEvalOut:
    req_id = str(req["id_solicitud"])
    req_dt = start_dt + timedelta(minutes=minute)
    rules = rules_by_urg.get(urgency, {})
    eligible: list[UnitStatusOut] = []
    excluded: list[ExclusionReason] = []
    compat: dict[str, int] = {}
    for unit in fleet.values():
        divert = _can_divert(unit, urgency, requests, codes)
        kind = _availability(unit, minute)
        if kind == "out" and not divert:
            excluded.append(
                ExclusionReason(
                    unit_id=unit.unit_id,
                    unit_type=unit.unit_type,
                    reason_codes=[],
                    reasons=[f"Estado escenario: {unit.state}"],
                )
            )
            continue
        if unit.unit_type not in rules:
            excluded.append(
                ExclusionReason(
                    unit_id=unit.unit_id,
                    unit_type=unit.unit_type,
                    reason_codes=[],
                    reasons=["No compatible"],
                )
            )
            continue
        row = units_db.get(unit.unit_id)
        busy_until = None
        if kind == "held":
            busy_until = req_dt + timedelta(minutes=unit.release_at - minute)
        eligible.append(
            UnitStatusOut(
                unit_id=unit.unit_id,
                unit_type=unit.unit_type,
                base_id=unit.base_id,
                shift="TURNO_24H",
                capacity=1,
                cost_per_km=row.cost_per_km if row else None,
                cost_per_hour=row.cost_per_hour if row else None,
                current_zone_id=unit.zone_id,
                active=True,
                simulated_available=kind == "free" or divert,
                busy_until=busy_until,
                workload_4h=0,
                workload_8h=0,
                workload_12h=0,
                diversion_of_service_id=unit.diversion_of if divert else None,
            )
        )
        compat[unit.unit_id] = rules[unit.unit_type]

    service = RawService(
        service_id=req_id,
        request_datetime=req_dt,
        urgency_level=urgency,
        service_type=str(req["motivo_consulta"]),
        discriminator=str(req["discriminador"]),
        zone_id=str(req["id_zona"]),
        status="PENDING",
        is_synthetic=True,
    )
    ranked = score_candidates(
        db,
        service,
        EligibilityEvaluation(
            service_id=req_id,
            evaluation_datetime=req_dt,
            eligible_units=eligible,
            excluded_units=excluded,
        ),
        compat,
        config.weight_time,
        config.weight_workload,
        config.weight_cost,
        config.weight_coverage,
    )
    top = ranked[0] if ranked else None
    ref_uid = ref.get("id_movil")
    ref_candidate = next((c for c in ranked if ref_uid and c.unit.unit_id == ref_uid), None)
    ref_utype = ref.get("tipo_movil")
    factors = list(top.factors) if top else []
    warnings = list(top.warnings) if top else []
    if top is not None:
        # R06: un desvío ofrecido que no es el Top 1 sigue visible como alternativa.
        for position, candidate in enumerate(ranked, start=1):
            origin = candidate.unit.diversion_of_service_id
            if origin and position > 1:
                warnings.append(
                    f"{r06_factor(candidate.unit.unit_id, origin)} (alternativa #{position})"
                )
    if top is not None and top.unit.current_zone_id:
        zone_factor = f"Zona de origen {top.unit.current_zone_id}"
        if zone_factor not in factors:
            factors.append(zone_factor)
    return ScenarioRequestEvalOut(
        id_solicitud=req_id,
        minuto_llegada=int(req["minuto_llegada"]),
        id_zona=str(req["id_zona"]),
        clasificacion_inicial=urgency,
        motivo_consulta=str(req["motivo_consulta"]),
        discriminador=str(req["discriminador"]),
        recommended_unit_id=top.unit.unit_id if top else None,
        recommended_unit_type=top.unit.unit_type if top else None,
        recommended_score=top.score if top else None,
        distance_km=top.distance_km if top else None,
        estimated_travel_min=top.estimated_travel_min if top else None,
        estimated_cost=top.estimated_cost if top else None,
        recommended_role=top.recommended_role if top else None,
        paired_unit_id=top.paired_unit_id if top else None,
        factors=factors,
        warnings=warnings,
        reference_unit_id=str(ref_uid) if ref_uid else None,
        reference_unit_type=str(ref_utype) if ref_utype else None,
        reference_role=str(ref["rol"]) if ref.get("rol") else None,
        reference_eta_min=float(ref["tiempo_estimado_llegada_min"])
        if ref.get("tiempo_estimado_llegada_min") is not None
        else None,
        reference_distance_km=ref_candidate.distance_km if ref_candidate else None,
        reference_estimated_cost=ref_candidate.estimated_cost if ref_candidate else None,
        reference_justification=str(ref["justificacion_despachador"])
        if ref.get("justificacion_despachador")
        else None,
        matches_reference_unit=bool(top and ref_uid and top.unit.unit_id == ref_uid),
        matches_reference_type=bool(top and ref_utype and top.unit.unit_type == ref_utype),
    )


def _availability(unit: _Unit, minute: int) -> str:
    if unit.state == "FUERA_SERVICIO":
        return "out"
    if unit.state in FREE_STATES:
        return "free"
    if unit.state == "EN_TRASLADO" and unit.release_at > minute:
        return "held"
    if unit.release_at > 0 and unit.release_at <= minute:
        return "free"
    return "out"


def _can_divert(
    unit: _Unit,
    urgency: str,
    requests: dict[str, dict[str, Any]],
    codes: dict[str, str],
) -> bool:
    if urgency not in VITAL_CODES or not unit.diversion_of:
        return False
    origin = requests.get(unit.diversion_of)
    return origin is not None and codes.get(unit.diversion_of) in DIVERTABLE_CODES
