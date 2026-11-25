"""Evaluación de los 14 escenarios de referencia y 12 KPIs de Grupo EMI."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any, Literal

import numpy as np
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.raw import RawResponseTarget, RawService, RawUnit
from app.schemas.benchmarks import (
    BaselineByClassificationOut,
    KpiDefinitionOut,
    KpisOverviewOut,
    ScenarioEvaluationOut,
    ScenarioRequestEvalOut,
    ScenarioSummaryOut,
)
from app.services.recommendation_service import retention_samples

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


def _observed_kpis(db: Session, targets: dict[str, int]) -> dict[str, str]:
    rows = db.execute(
        select(
            RawService.request_datetime,
            RawService.dispatch_datetime,
            RawService.assignment_datetime,
            RawService.urgency_level,
            RawService.response_time_min,
            RawService.reported_response_min,
            RawService.distance_km,
            RawService.closure_state,
            RawService.classifications_json,
            RawService.assigned_units_json,
        ).where(RawService.is_synthetic.is_(False))
    ).all()
    units = db.execute(select(RawUnit)).scalars().all()
    unit_type_by_id = {u.unit_id: u.unit_type for u in units}
    unit_costs = {u.unit_id: (u.cost_per_km or 0.0, u.cost_per_hour or 0.0) for u in units}

    by_urg: dict[str, list[float]] = {}
    assign_wait_vital: list[float] = []
    busy_hours_by_unit: dict[str, float] = {u.unit_id: 0.0 for u in units}
    count_by_unit: dict[str, int] = {u.unit_id: 0 for u in units}
    distances: list[float] = []
    costs: list[float] = []
    cancelled_count = 0
    reclass_count = 0
    vital_total = 0
    vital_r04 = 0
    min_dt: datetime | None = None
    max_dt: datetime | None = None

    for (
        req_dt,
        disp_dt,
        assign_dt,
        urg,
        rt_calc,
        rt_rep,
        dist_km,
        closure_state,
        classifications,
        assigned_units,
    ) in rows:
        if min_dt is None or req_dt < min_dt:
            min_dt = req_dt
        if max_dt is None or req_dt > max_dt:
            max_dt = req_dt

        val = rt_rep if rt_rep is not None else rt_calc
        if val is not None:
            by_urg.setdefault(urg, []).append(float(val))

        if urg in ("01", "02"):
            vital_total += 1
            if disp_dt is not None and assign_dt is not None:
                wait_min = (assign_dt - disp_dt).total_seconds() / 60.0
                if wait_min >= 0:
                    assign_wait_vital.append(wait_min)

        if closure_state == "CANCELADO_POR_USUARIO":
            cancelled_count += 1
        if isinstance(classifications, list) and len(classifications) > 1:
            reclass_count += 1

        if isinstance(assigned_units, list) and assigned_units:
            service_has_r04 = False
            service_cost = 0.0
            service_km = 0.0
            for entry in assigned_units:
                if not isinstance(entry, dict):
                    continue
                uid = str(entry.get("id_movil") or "")
                if entry.get("rol") == "PRIMER_RESPONDIENTE_ESTABILIZACION":
                    service_has_r04 = True
                if uid in count_by_unit:
                    count_by_unit[uid] += 1
                ekm = float(entry.get("distancia_km") or 0.0)
                service_km += ekm
                a_str = entry.get("fecha_hora_asignacion")
                l_str = entry.get("fecha_hora_liberacion")
                occ_hrs = 0.0
                if a_str and l_str:
                    occ_hrs = max(
                        0.0,
                        (
                            datetime.fromisoformat(str(l_str)) - datetime.fromisoformat(str(a_str))
                        ).total_seconds()
                        / 3600.0,
                    )
                    if uid in busy_hours_by_unit:
                        busy_hours_by_unit[uid] += occ_hrs
                c_km, c_hr = unit_costs.get(uid, (0.0, 0.0))
                service_cost += ekm * c_km + occ_hrs * c_hr
            if urg in ("01", "02") and service_has_r04:
                vital_r04 += 1
            if service_km > 0:
                distances.append(service_km)
            elif dist_km is not None:
                distances.append(float(dist_km))
            if service_cost > 0:
                costs.append(service_cost)
        elif dist_km is not None:
            distances.append(float(dist_km))

    live: dict[str, str] = {}
    if by_urg.get("01"):
        live["KPI-01"] = f"{np.percentile(by_urg['01'], 90):.1f}"
    if by_urg.get("02"):
        live["KPI-02"] = f"{np.percentile(by_urg['02'], 90):.1f}"
    if by_urg:
        parts = []
        for code in ("01", "02", "07", "03", "06"):
            vals = by_urg.get(code, [])
            if vals:
                tgt = targets.get(code, 30)
                pct = 100.0 * sum(1 for v in vals if v <= tgt) / len(vals)
                parts.append(f"{code}: {pct:.1f}%")
        if parts:
            live["KPI-03"] = " / ".join(parts)

    if assign_wait_vital:
        live["KPI-04"] = f"{float(median(assign_wait_vital)):.1f} min (mediana 01/02)"

    period_hours = (
        max(1.0, (max_dt - min_dt).total_seconds() / 3600.0) if min_dt and max_dt else 1.0
    )
    util_parts: list[str] = []
    cv_parts: list[str] = []
    for utype in ("TAM", "TAB", "VMD"):
        uids = [uid for uid, t in unit_type_by_id.items() if t == utype]
        if not uids:
            continue
        utils = [100.0 * busy_hours_by_unit[uid] / period_hours for uid in uids]
        util_parts.append(f"{utype}: {float(np.mean(utils)):.1f}%")
        counts = [float(count_by_unit[uid]) for uid in uids]
        mean_c = float(np.mean(counts))
        cv = float(np.std(counts)) / mean_c if mean_c > 0 else 0.0
        cv_parts.append(f"{utype}: {cv:.2f}")
    if util_parts:
        live["KPI-05"] = " / ".join(util_parts)
    if cv_parts:
        live["KPI-06"] = " / ".join(cv_parts)

    if distances:
        live["KPI-07"] = f"{float(np.mean(distances)):.2f}"
    if costs:
        live["KPI-08"] = f"{float(np.mean(costs)):,.0f}"

    total_rows = len(rows)
    if total_rows > 0:
        live["KPI-09"] = f"{100.0 * cancelled_count / total_rows:.2f}%"
        live["KPI-12"] = f"{100.0 * reclass_count / total_rows:.2f}%"
    if vital_total > 0:
        live["KPI-10"] = f"{100.0 * vital_r04 / vital_total:.2f}%"

    by_center, all_ret = retention_samples(db)
    if all_ret:
        global_med = float(median(all_ret))
        center_meds = [
            (float(median(vals)), name) for name, vals in by_center.items() if len(vals) >= 5
        ]
        if len(center_meds) >= 2:
            center_meds.sort()
            lo_val, lo_name = center_meds[0]
            hi_val, hi_name = center_meds[-1]
            live["KPI-11"] = (
                f"{global_med:.1f} min (mín {lo_name}: {lo_val:.1f} / máx {hi_name}: {hi_val:.1f})"
            )
        else:
            live["KPI-11"] = f"{global_med:.1f} min"

    return live


def _simulated_kpis(
    db: Session, targets: dict[str, int]
) -> tuple[dict[str, str], dict[str, Literal["SIMULADO", "OBSERVADO"]]]:
    from app.services.scenario_replay import replay_scenario

    all_results: list[ScenarioRequestEvalOut] = []
    for sc in list_scenarios():
        all_results.extend(replay_scenario(db, sc.id_escenario).results)

    sim_by_urg: dict[str, list[float]] = {}
    sug_km: list[float] = []
    ref_km: list[float] = []
    sug_cost: list[float] = []
    ref_cost: list[float] = []
    vital_total = 0
    vital_r04 = 0

    for r in all_results:
        urg = r.clasificacion_inicial
        if r.estimated_travel_min is not None:
            sim_by_urg.setdefault(urg, []).append(float(r.estimated_travel_min))
        if r.distance_km is not None:
            sug_km.append(float(r.distance_km))
        if r.reference_distance_km is not None:
            ref_km.append(float(r.reference_distance_km))
        if r.estimated_cost is not None:
            sug_cost.append(float(r.estimated_cost))
        if r.reference_estimated_cost is not None:
            ref_cost.append(float(r.reference_estimated_cost))
        if urg in ("01", "02"):
            vital_total += 1
            if r.recommended_role == "PRIMER_RESPONDIENTE_ESTABILIZACION":
                vital_r04 += 1

    sim: dict[str, str] = {}
    prov: dict[str, Literal["SIMULADO", "OBSERVADO"]] = {}

    if sim_by_urg.get("01"):
        sim["KPI-01"] = f"{np.percentile(sim_by_urg['01'], 90):.1f}"
        prov["KPI-01"] = "SIMULADO"
    if sim_by_urg.get("02"):
        sim["KPI-02"] = f"{np.percentile(sim_by_urg['02'], 90):.1f}"
        prov["KPI-02"] = "SIMULADO"
    if sim_by_urg:
        parts = []
        for code in ("01", "02", "07", "03", "06"):
            vals = sim_by_urg.get(code, [])
            if vals:
                tgt = targets.get(code, 30)
                pct = 100.0 * sum(1 for v in vals if v <= tgt) / len(vals)
                parts.append(f"{code}: {pct:.1f}%")
        if parts:
            sim["KPI-03"] = " / ".join(parts)
            prov["KPI-03"] = "SIMULADO"

    if sug_km:
        ref_txt = f"{float(np.mean(ref_km)):.2f}" if ref_km else "N/D"
        sim["KPI-07"] = f"sugerido {float(np.mean(sug_km)):.2f} / referencia {ref_txt}"
        prov["KPI-07"] = "SIMULADO"
    if sug_cost:
        ref_txt = f"{float(np.mean(ref_cost)):,.0f}" if ref_cost else "N/D"
        sim["KPI-08"] = f"sugerido {float(np.mean(sug_cost)):,.0f} / referencia {ref_txt}"
        prov["KPI-08"] = "SIMULADO"
    if vital_total > 0:
        sim["KPI-10"] = f"{100.0 * vital_r04 / vital_total:.1f}%"
        prov["KPI-10"] = "SIMULADO"

    return sim, prov


def get_kpis_overview(db: Session) -> KpisOverviewOut:
    kpis_raw, base_raw = _load_indicators_workbook()
    targets = {
        t.urgency_level: t.target_response_min
        for t in db.execute(select(RawResponseTarget)).scalars()
    }
    live_map = _observed_kpis(db, targets)
    sim_map, sim_prov = _simulated_kpis(db, targets)

    kpis = [
        KpiDefinitionOut(
            id_kpi=str(r["id_kpi"]),
            nombre=str(r["nombre"]),
            definicion=str(r["definicion"]),
            unidad=str(r["unidad"]),
            meta_referencia=str(r["meta_referencia"]),
            linea_base_ficticia=str(r["linea_base_ficticia"]),
            valor_actual_db=live_map.get(str(r["id_kpi"])),
            valor_simulado=sim_map.get(str(r["id_kpi"])),
            procedencia_simulado=sim_prov.get(str(r["id_kpi"])),
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
    from app.services.scenario_replay import replay_scenario

    return replay_scenario(db, scenario_id)
