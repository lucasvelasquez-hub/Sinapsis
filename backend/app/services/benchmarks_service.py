"""Evaluación de los 14 escenarios de referencia y 12 KPIs de Grupo EMI."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.raw import RawResponseTarget, RawService, RawServiceRule, RawUnit
from app.schemas.benchmarks import (
    BaselineByClassificationOut,
    KpiDefinitionOut,
    KpisOverviewOut,
    ScenarioEvaluationOut,
    ScenarioRequestEvalOut,
    ScenarioSummaryOut,
)
from app.schemas.dispatch import EligibilityEvaluation, ExclusionReason, UnitStatusOut
from app.services.recommendation_service import score_candidates
from app.services.scoring_service import get_scoring_config

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
AVAILABLE_SCENARIO_STATES = {"DISPONIBLE", "RETORNANDO"}


def _sheet_dicts(wb: openpyxl.Workbook, sheet: str) -> list[dict[str, Any]]:
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) for h in rows[0]]
    return [dict(zip(headers, r, strict=False)) for r in rows[1:] if any(v is not None for v in r)]


@lru_cache(maxsize=1)
def _load_indicators_workbook() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wb = openpyxl.load_workbook(RAW_DIR / "07_indicadores.xlsx", read_only=True, data_only=True)
    kpis = _sheet_dicts(wb, "kpis")
    baseline = _sheet_dicts(wb, "linea_base_por_clasificacion")
    wb.close()
    return kpis, baseline


@lru_cache(maxsize=1)
def _load_scenarios_workbook() -> dict[str, list[dict[str, Any]]]:
    wb = openpyxl.load_workbook(
        RAW_DIR / "06_escenarios_referencia.xlsx", read_only=True, data_only=True
    )
    data = {
        sh: _sheet_dicts(wb, sh)
        for sh in (
            "escenarios",
            "estado_inicial_moviles",
            "solicitudes",
            "eventos",
            "decision_despachador",
        )
    }
    wb.close()
    return data


def get_kpis_overview(db: Session) -> KpisOverviewOut:
    kpis_raw, base_raw = _load_indicators_workbook()
    rows = db.execute(
        select(
            RawService.urgency_level,
            RawService.response_time_min,
            RawService.reported_response_min,
        ).where(RawService.is_synthetic.is_(False))
    ).all()
    targets = {
        t.urgency_level: t.target_response_min
        for t in db.execute(select(RawResponseTarget)).scalars()
    }

    by_urg: dict[str, list[float]] = {}
    for urg, rt_calc, rt_rep in rows:
        val = rt_rep if rt_rep is not None else rt_calc
        if val is not None:
            by_urg.setdefault(urg, []).append(float(val))

    live_map: dict[str, str] = {}
    if by_urg.get("01"):
        live_map["KPI-01"] = f"{np.percentile(by_urg['01'], 90):.1f}"
    if by_urg.get("02"):
        live_map["KPI-02"] = f"{np.percentile(by_urg['02'], 90):.1f}"
    if by_urg:
        parts = []
        for code in ("01", "02", "07", "03", "06"):
            vals = by_urg.get(code, [])
            if vals:
                tgt = targets.get(code, 30)
                pct = 100.0 * sum(1 for v in vals if v <= tgt) / len(vals)
                parts.append(f"{code}: {pct:.1f}%")
        if parts:
            live_map["KPI-03"] = " / ".join(parts)

    kpis = [
        KpiDefinitionOut(
            id_kpi=str(r["id_kpi"]),
            nombre=str(r["nombre"]),
            definicion=str(r["definicion"]),
            unidad=str(r["unidad"]),
            meta_referencia=str(r["meta_referencia"]),
            linea_base_ficticia=str(r["linea_base_ficticia"]),
            valor_actual_db=live_map.get(str(r["id_kpi"])),
        )
        for r in kpis_raw
    ]
    baseline = [
        BaselineByClassificationOut(
            clasificacion=str(r["clasificacion"]),
            descripcion=str(r["descripcion"]),
            escala_manchester=str(r["escala_manchester"]),
            servicios=int(r["servicios"]),
            tiempo_objetivo_min=int(r["tiempo_objetivo_min"]),
            tr_mediana_min=float(r["tr_mediana_min"]),
            tr_promedio_min=float(r["tr_promedio_min"]),
            tr_p90_min=float(r["tr_p90_min"]),
            pct_cumple_objetivo=float(r["pct_cumple_objetivo"]),
            pct_traslado=float(r["pct_traslado"]),
        )
        for r in base_raw
    ]
    return KpisOverviewOut(kpis=kpis, linea_base=baseline)


def list_scenarios() -> list[ScenarioSummaryOut]:
    data = _load_scenarios_workbook()
    return [
        ScenarioSummaryOut(
            id_escenario=str(r["id_escenario"]),
            nombre=str(r["nombre"]),
            descripcion=str(r["descripcion"]),
            fecha_hora_inicio=str(r["fecha_hora_inicio"]),
            tipo_dia=str(r["tipo_dia"]),
            duracion_min=int(r["duracion_min"]),
            factor_trafico_inicio=float(r["factor_trafico_inicio"]),
            objetivo_aprendizaje=str(r["objetivo_aprendizaje"]),
            n_solicitudes=int(r["n_solicitudes"]),
        )
        for r in data["escenarios"]
    ]


def evaluate_scenario(db: Session, scenario_id: str) -> ScenarioEvaluationOut:
    scenarios = {s.id_escenario: s for s in list_scenarios()}
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise ResourceNotFoundError("Scenario", scenario_id)

    data = _load_scenarios_workbook()
    fleet_snap = [r for r in data["estado_inicial_moviles"] if r["id_escenario"] == scenario_id]
    requests = [r for r in data["solicitudes"] if r["id_escenario"] == scenario_id]
    ref_decisions = {
        r["id_solicitud"]: r
        for r in data["decision_despachador"]
        if r["id_escenario"] == scenario_id and int(r.get("orden_movil") or 1) == 1
    }

    units_db = {u.unit_id: u for u in db.execute(select(RawUnit)).scalars().all()}
    rules_by_urg: dict[str, dict[str, int]] = {}
    eligible_rules = db.execute(
        select(RawServiceRule).where(RawServiceRule.eligible.is_(True))
    ).scalars()
    for rule in eligible_rules:
        rules_by_urg.setdefault(rule.urgency_level, {})[rule.unit_type] = rule.compatibility_rank

    cfg = get_scoring_config(db)
    start_dt = datetime.strptime(scenario.fecha_hora_inicio, "%Y-%m-%d %H:%M")

    results: list[ScenarioRequestEvalOut] = []
    unit_matches = 0
    type_matches = 0

    for req in requests:
        req_id = str(req["id_solicitud"])
        min_arr = int(req["minuto_llegada"])
        req_dt = start_dt + timedelta(minutes=min_arr)
        urg = str(req["clasificacion_inicial"])
        rules = rules_by_urg.get(urg, {})

        eligible_units: list[UnitStatusOut] = []
        excluded_units: list[ExclusionReason] = []
        compat_ranks: dict[str, int] = {}

        for snap in fleet_snap:
            uid = str(snap["id_movil"])
            utype = str(snap["tipo_movil"])
            state = str(snap["estado"])
            free_in = float(snap.get("min_para_liberarse") or 0)
            is_avail = state in AVAILABLE_SCENARIO_STATES or (free_in > 0 and free_in <= min_arr)
            u_db = units_db.get(uid)

            if not is_avail or utype not in rules:
                excluded_units.append(
                    ExclusionReason(
                        unit_id=uid,
                        unit_type=utype,
                        reason_codes=[],
                        reasons=[f"Estado escenario: {state}" if not is_avail else "No compatible"],
                    )
                )
                continue

            eligible_units.append(
                UnitStatusOut(
                    unit_id=uid,
                    unit_type=utype,
                    base_id=str(snap["id_base"]),
                    shift="TURNO_24H",
                    capacity=1,
                    cost_per_km=u_db.cost_per_km if u_db else None,
                    cost_per_hour=u_db.cost_per_hour if u_db else None,
                    current_zone_id=str(snap["id_zona_actual"]),
                    active=True,
                    simulated_available=True,
                    busy_until=None,
                    workload_4h=0,
                    workload_8h=0,
                    workload_12h=0,
                )
            )
            compat_ranks[uid] = rules[utype]

        fake_service = RawService(
            service_id=req_id,
            request_datetime=req_dt,
            urgency_level=urg,
            service_type=str(req["motivo_consulta"]),
            zone_id=str(req["id_zona"]),
            status="PENDING",
            is_synthetic=True,
        )
        elig = EligibilityEvaluation(
            service_id=req_id,
            evaluation_datetime=req_dt,
            eligible_units=eligible_units,
            excluded_units=excluded_units,
        )
        ranked = score_candidates(
            db,
            fake_service,
            elig,
            compat_ranks,
            cfg.weight_time,
            cfg.weight_workload,
            cfg.weight_cost,
            cfg.weight_coverage,
        )
        top1 = ranked[0] if ranked else None
        ref = ref_decisions.get(req_id, {})
        ref_uid = ref.get("id_movil")
        ref_utype = ref.get("tipo_movil")

        u_match = bool(top1 and ref_uid and top1.unit.unit_id == ref_uid)
        t_match = bool(top1 and ref_utype and top1.unit.unit_type == ref_utype)
        if u_match:
            unit_matches += 1
        if t_match:
            type_matches += 1

        results.append(
            ScenarioRequestEvalOut(
                id_solicitud=req_id,
                minuto_llegada=min_arr,
                id_zona=str(req["id_zona"]),
                clasificacion_inicial=urg,
                motivo_consulta=str(req["motivo_consulta"]),
                discriminador=str(req["discriminador"]),
                recommended_unit_id=top1.unit.unit_id if top1 else None,
                recommended_unit_type=top1.unit.unit_type if top1 else None,
                recommended_score=top1.score if top1 else None,
                distance_km=top1.distance_km if top1 else None,
                estimated_travel_min=top1.estimated_travel_min if top1 else None,
                estimated_cost=top1.estimated_cost if top1 else None,
                recommended_role=top1.recommended_role if top1 else None,
                paired_unit_id=top1.paired_unit_id if top1 else None,
                factors=top1.factors if top1 else [],
                warnings=top1.warnings if top1 else [],
                reference_unit_id=str(ref_uid) if ref_uid else None,
                reference_unit_type=str(ref_utype) if ref_utype else None,
                reference_role=str(ref["rol"]) if ref.get("rol") else None,
                reference_eta_min=float(ref["tiempo_estimado_llegada_min"])
                if ref.get("tiempo_estimado_llegada_min") is not None
                else None,
                reference_justification=str(ref["justificacion_despachador"])
                if ref.get("justificacion_despachador")
                else None,
                matches_reference_unit=u_match,
                matches_reference_type=t_match,
            )
        )

    total = len(results) or 1
    return ScenarioEvaluationOut(
        scenario=scenario,
        results=results,
        unit_match_rate=round(unit_matches / total, 4),
        type_match_rate=round(type_matches / total, 4),
    )
