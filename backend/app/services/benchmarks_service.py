"""Evaluación de los 14 escenarios de referencia y 12 KPIs de Grupo EMI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.raw import RawResponseTarget, RawService
from app.schemas.benchmarks import (
    BaselineByClassificationOut,
    KpiDefinitionOut,
    KpisOverviewOut,
    ScenarioEvaluationOut,
    ScenarioSummaryOut,
)

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
    from app.services.scenario_replay import replay_scenario

    return replay_scenario(db, scenario_id)
