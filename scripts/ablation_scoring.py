"""Auditoría de reglas EMI y ablación comparativa sobre los 14 escenarios.

Compara sin modificar la DB:
  1. REFERENCIA_DESPACHADOR (decisiones del Excel 06_escenarios_referencia.xlsx)
  2. GREEDY_ETA (móvil compatible libre más cercano, sin política EMI)
  3. CORE_ACTUAL (política EMI D01-D08 / R01-R07 + scoring compuesto)

Uso (desde backend/):
    DATABASE_URL=postgresql+psycopg://core_user:core_password@localhost:5433/core_db \\
      uv run python ../scripts/ablation_scoring.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.domain.assignment_policy import WARN_D03, WARN_D05, WARN_D06  # noqa: E402
from app.models.raw import RawResponseTarget, RawServiceRule, RawUnit  # noqa: E402
from app.schemas.benchmarks import ScenarioEvaluationOut  # noqa: E402
from app.services.benchmarks_service import _load_scenarios_workbook, list_scenarios  # noqa: E402
from app.services.recommendation_service import _traffic_factor, _travel_lookup  # noqa: E402
from app.services.scenario_replay import (  # noqa: E402
    DEFAULT_TARGETS,
    SERVICE_DURATION_MIN,
    _apply_event,
    _availability,
    _occupy_unit,
    _release_previous_assignment,
    _Unit,
    replay_scenario,
)


def _cv(counts: Counter[str]) -> float:
    if not counts:
        return 0.0
    vals = [float(v) for v in counts.values()]
    mean_v = float(np.mean(vals))
    if mean_v <= 0:
        return 0.0
    return round(float(np.std(vals)) / mean_v, 3)


def _mean_or_none(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(float(np.mean(vals)), 2)


def _pct(hits: int, total: int) -> float:
    return round(100.0 * hits / max(1, total), 1)


def _pick_greedy_for_request(
    db: Session,
    req: dict[str, Any],
    minute: int,
    start_dt: datetime,
    fleet: dict[str, _Unit],
    codes: dict[str, str],
    rules_by_urg: dict[str, set[str]],
    units_db: dict[str, RawUnit],
    picked: dict[str, dict[str, Any]],
) -> None:
    req_id = str(req["id_solicitud"])
    _release_previous_assignment(fleet, req_id)
    urg = codes[req_id]
    allowed = rules_by_urg.get(urg, set())
    when = start_dt + timedelta(minutes=minute)
    traffic = _traffic_factor(db, when)
    dest_zone = str(req["id_zona"])
    free_units = [
        u
        for u in fleet.values()
        if u.unit_type in allowed
        and u.state != "FUERA_SERVICIO"
        and _availability(u, minute) == "free"
    ]
    zones = {u.zone_id for u in free_units}
    travel = _travel_lookup(db, zones, dest_zone)
    best_u: _Unit | None = None
    best_eta = float("inf")
    best_km = 0.0
    for u in free_units:
        tr = travel.get(u.zone_id)
        if tr is None:
            continue
        dist_km, base_min = float(tr[0]), float(tr[1])
        eta = round(base_min * traffic, 2) + 2.0
        tie_better = best_u is None or u.unit_id < best_u.unit_id
        if eta < best_eta or (eta == best_eta and tie_better):
            best_u = u
            best_eta = eta
            best_km = dist_km
    if best_u is not None:
        db_u = units_db.get(best_u.unit_id)
        c_km = float(db_u.cost_per_km or 0.0) if db_u else 0.0
        c_hr = float(db_u.cost_per_hour or 0.0) if db_u else 0.0
        dur_hr = (best_eta + SERVICE_DURATION_MIN.get(urg, 25.0)) / 60.0
        cost = round(best_km * c_km + dur_hr * c_hr, 2)
        _occupy_unit(best_u, req_id, dest_zone, urg, minute, best_eta)
        picked[req_id] = {
            "unit_id": best_u.unit_id,
            "unit_type": best_u.unit_type,
            "urg": urg,
            "eta": best_eta,
            "km": best_km,
            "cost": cost,
        }
    else:
        picked[req_id] = {
            "unit_id": None,
            "unit_type": None,
            "urg": urg,
            "eta": None,
            "km": None,
            "cost": None,
        }


def _run_greedy_baseline(
    db: Session,
    targets: dict[str, int],
    rules_by_urg: dict[str, set[str]],
    units_db: dict[str, RawUnit],
) -> dict[str, Any]:
    """Replay cronológico con ocupación de flota eligiendo solo el menor ETA compatible."""
    data = _load_scenarios_workbook()
    etas: list[float] = []
    vital_etas: list[float] = []
    dists: list[float] = []
    costs: list[float] = []
    sla_hits = 0
    sla_n = 0
    vital_hits = 0
    vital_n = 0
    unit_matches = 0
    type_matches = 0
    total_req = 0
    usage: Counter[str] = Counter()

    for sc in list_scenarios():
        sc_id = sc.id_escenario
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
            if row["id_escenario"] == sc_id
        }
        requests = [row for row in data["solicitudes"] if row["id_escenario"] == sc_id]
        events = [row for row in data["eventos"] if row["id_escenario"] == sc_id]
        by_req = {str(r["id_solicitud"]): r for r in requests}
        codes = {str(r["id_solicitud"]): str(r["clasificacion_inicial"]) for r in requests}
        ref_dec = {
            str(r["id_solicitud"]): r
            for r in data["decision_despachador"]
            if r["id_escenario"] == sc_id and int(r.get("orden_movil") or 1) == 1
        }
        start_dt = datetime.strptime(sc.fecha_hora_inicio, "%Y-%m-%d %H:%M")

        timeline: list[tuple[int, int, str, Any]] = []
        for req in requests:
            timeline.append((int(req["minuto_llegada"]), 1, "req", req))
        for ev in events:
            timeline.append((int(ev["minuto"]), 0, "event", ev))
        timeline.sort(key=lambda item: (item[0], item[1]))

        cancelled: set[str] = set()
        picked: dict[str, dict[str, Any]] = {}

        for _minute, _ord, kind, item in timeline:
            if kind == "req":
                _pick_greedy_for_request(
                    db,
                    item,
                    int(item["minuto_llegada"]),
                    start_dt,
                    fleet,
                    codes,
                    rules_by_urg,
                    units_db,
                    picked,
                )
            else:
                _apply_event(item, fleet, by_req, codes, cancelled)
                reclass_kinds = ("RECLASIFICACION_EN_SITIO", "RECLASIFICACION_TELEFONICA")
                if item["tipo_evento"] in reclass_kinds:
                    target = by_req.get(str(item["id_solicitud"]))
                    if target is not None:
                        _pick_greedy_for_request(
                            db,
                            target,
                            int(item["minuto"]),
                            start_dt,
                            fleet,
                            codes,
                            rules_by_urg,
                            units_db,
                            picked,
                        )

        for req in requests:
            req_id = str(req["id_solicitud"])
            total_req += 1
            p = picked.get(req_id, {})
            ref = ref_dec.get(req_id, {})
            urg = str(p.get("urg") or codes[req_id])
            tgt = targets.get(urg, 30)
            if p.get("unit_id"):
                usage[str(p["unit_id"])] += 1
            if p.get("eta") is not None:
                val = float(p["eta"])
                etas.append(val)
                sla_n += 1
                if val <= tgt:
                    sla_hits += 1
                if urg in ("01", "02"):
                    vital_etas.append(val)
                    vital_n += 1
                    if val <= tgt:
                        vital_hits += 1
            if p.get("km") is not None:
                dists.append(float(p["km"]))
            if p.get("cost") is not None:
                costs.append(float(p["cost"]))
            if p.get("unit_id") and ref.get("id_movil") and p["unit_id"] == str(ref["id_movil"]):
                unit_matches += 1
            if (
                p.get("unit_type")
                and ref.get("tipo_movil")
                and p["unit_type"] == str(ref["tipo_movil"])
            ):
                type_matches += 1

    return {
        "strategy": "GREEDY_ETA",
        "total_requests": total_req,
        "avg_eta_min": _mean_or_none(etas),
        "p90_vital_min": round(float(np.percentile(vital_etas, 90)), 2) if vital_etas else None,
        "sla_pct": _pct(sla_hits, sla_n),
        "sla_vital_pct": _pct(vital_hits, vital_n),
        "avg_dist_km": _mean_or_none(dists),
        "avg_cost_cop": _mean_or_none(costs),
        "workload_cv": _cv(usage),
        "type_match_pct": _pct(type_matches, total_req),
        "unit_match_pct": _pct(unit_matches, total_req),
    }


def _summarize_core_and_ref(
    evals: list[ScenarioEvaluationOut],
    targets: dict[str, int],
    rules_by_urg: dict[str, set[str]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    core_etas: list[float] = []
    core_vital: list[float] = []
    core_dists: list[float] = []
    core_costs: list[float] = []
    core_sla_hits = 0
    core_sla_n = 0
    core_vital_hits = 0
    core_vital_n = 0
    core_usage: Counter[str] = Counter()
    unit_matches = 0
    type_matches = 0

    ref_etas: list[float] = []
    ref_vital: list[float] = []
    ref_dists: list[float] = []
    ref_costs: list[float] = []
    ref_sla_hits = 0
    ref_sla_n = 0
    ref_vital_hits = 0
    ref_vital_n = 0
    ref_usage: Counter[str] = Counter()

    total_req = 0
    r01_incompat = 0
    r03_vital_no_amb = 0
    r04_stab = 0
    r06_divert = 0
    d03_green = 0
    d05_tam_02 = 0
    d06_tab_07 = 0

    for ev in evals:
        for r in ev.results:
            total_req += 1
            urg = r.clasificacion_inicial
            tgt = targets.get(urg, 30)

            if r.recommended_unit_id:
                core_usage[r.recommended_unit_id] += 1
            if r.matches_reference_unit:
                unit_matches += 1
            if r.matches_reference_type:
                type_matches += 1

            if r.estimated_travel_min is not None:
                val = float(r.estimated_travel_min)
                core_etas.append(val)
                core_sla_n += 1
                if val <= tgt:
                    core_sla_hits += 1
                if urg in ("01", "02"):
                    core_vital.append(val)
                    core_vital_n += 1
                    if val <= tgt:
                        core_vital_hits += 1
            if r.distance_km is not None:
                core_dists.append(float(r.distance_km))
            if r.estimated_cost is not None:
                core_costs.append(float(r.estimated_cost))

            if r.reference_unit_id:
                ref_usage[r.reference_unit_id] += 1
            if r.reference_eta_min is not None:
                vref = float(r.reference_eta_min)
                ref_etas.append(vref)
                ref_sla_n += 1
                if vref <= tgt:
                    ref_sla_hits += 1
                if urg in ("01", "02"):
                    ref_vital.append(vref)
                    ref_vital_n += 1
                    if vref <= tgt:
                        ref_vital_hits += 1
            if r.reference_distance_km is not None:
                ref_dists.append(float(r.reference_distance_km))
            if r.reference_estimated_cost is not None:
                ref_costs.append(float(r.reference_estimated_cost))

            # Auditoría de reglas EMI
            allowed = rules_by_urg.get(urg, set())
            if r.recommended_unit_type and r.recommended_unit_type not in allowed:
                r01_incompat += 1
            if urg in ("01", "02") and r.recommended_unit_type == "VMD" and not r.paired_unit_id:
                r03_vital_no_amb += 1
            if r.recommended_role == "PRIMER_RESPONDIENTE_ESTABILIZACION":
                r04_stab += 1
            if any(w.startswith("Regla R06:") for w in (*r.factors, *r.warnings)):
                r06_divert += 1
            if urg in ("07", "03", "06") and WARN_D03 in r.warnings:
                d03_green += 1
            if urg == "02" and WARN_D05 in r.warnings:
                d05_tam_02 += 1
            if urg == "07" and WARN_D06 in r.warnings:
                d06_tab_07 += 1

    ref_row = {
        "strategy": "REFERENCIA_DESPACHADOR",
        "total_requests": total_req,
        "avg_eta_min": _mean_or_none(ref_etas),
        "p90_vital_min": round(float(np.percentile(ref_vital, 90)), 2) if ref_vital else None,
        "sla_pct": _pct(ref_sla_hits, ref_sla_n),
        "sla_vital_pct": _pct(ref_vital_hits, ref_vital_n),
        "avg_dist_km": _mean_or_none(ref_dists),
        "avg_cost_cop": _mean_or_none(ref_costs),
        "workload_cv": _cv(ref_usage),
        "type_match_pct": 100.0,
        "unit_match_pct": 100.0,
    }
    core_row = {
        "strategy": "CORE_ACTUAL",
        "total_requests": total_req,
        "avg_eta_min": _mean_or_none(core_etas),
        "p90_vital_min": round(float(np.percentile(core_vital, 90)), 2) if core_vital else None,
        "sla_pct": _pct(core_sla_hits, core_sla_n),
        "sla_vital_pct": _pct(core_vital_hits, core_vital_n),
        "avg_dist_km": _mean_or_none(core_dists),
        "avg_cost_cop": _mean_or_none(core_costs),
        "workload_cv": _cv(core_usage),
        "type_match_pct": _pct(type_matches, total_req),
        "unit_match_pct": _pct(unit_matches, total_req),
    }
    audit = {
        "total_requests": total_req,
        "r01_incompatible_count": r01_incompat,
        "r03_vital_without_ambulance_or_pair": r03_vital_no_amb,
        "r04_stabilization_count": r04_stab,
        "r06_diversion_detected_count": r06_divert,
        "d03_green_uncovered_warnings": d03_green,
        "d05_tam_on_02_warnings": d05_tam_02,
        "d06_transfer_tab_activations": d06_tab_07,
    }
    return ref_row, core_row, audit


def run_ablation(db: Session) -> dict[str, Any]:
    targets = dict(DEFAULT_TARGETS)
    for row in db.execute(select(RawResponseTarget)).scalars():
        targets[row.urgency_level] = int(row.target_response_min)
    rules_by_urg: dict[str, set[str]] = {}
    for rule in db.execute(
        select(RawServiceRule).where(RawServiceRule.eligible.is_(True))
    ).scalars():
        rules_by_urg.setdefault(rule.urgency_level, set()).add(rule.unit_type)
    units_db = {u.unit_id: u for u in db.execute(select(RawUnit)).scalars().all()}

    evals = [replay_scenario(db, sc.id_escenario) for sc in list_scenarios()]
    ref_row, core_row, audit = _summarize_core_and_ref(evals, targets, rules_by_urg)
    greedy_row = _run_greedy_baseline(db, targets, rules_by_urg, units_db)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provenance": "SIMULADO",
        "strategies": [ref_row, greedy_row, core_row],
        "rule_audit": audit,
    }


def render_ablation_markdown(out: dict[str, Any]) -> str:
    hdr = (
        "| Estrategia | ETA Prom. | P90 Vital (01/02) | SLA Global | SLA Vital "
        "| Dist. km | Costo COP | CV Carga | Match Tipo | Match Móvil |"
    )
    lines = [
        "## Ablación Comparativa (14 Escenarios · 58 Solicitudes)",
        "",
        hdr,
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in out["strategies"]:
        eta = f"{s['avg_eta_min']:.1f}m" if s["avg_eta_min"] is not None else "N/D"
        p90 = f"{s['p90_vital_min']:.1f}m" if s["p90_vital_min"] is not None else "N/D"
        dist = f"{s['avg_dist_km']:.2f}" if s["avg_dist_km"] is not None else "N/D"
        cost = f"${s['avg_cost_cop']:,.0f}" if s["avg_cost_cop"] is not None else "N/D"
        lines.append(
            f"| `{s['strategy']}` | {eta} | {p90} | {s['sla_pct']:.1f}% "
            f"| {s['sla_vital_pct']:.1f}% | {dist} | {cost} | {s['workload_cv']:.3f} "
            f"| {s['type_match_pct']:.1f}% | {s['unit_match_pct']:.1f}% |"
        )
    a = out["rule_audit"]
    lines.extend(
        [
            "",
            "### Auditoría de Reglas EMI sobre CORE (58 solicitudes)",
            "",
            f"- **R01 (Compatibilidad clínica):** {a['r01_incompatible_count']} violaciones",
            f"- **R03 (Vital 01/02 sin ambulancia ni pareja):** "
            f"{a['r03_vital_without_ambulance_or_pair']} violaciones",
            f"- **R04 (Estabilización primer respondiente VMD + amb.):** "
            f"{a['r04_stabilization_count']} activaciones",
            f"- **R06 (Desvío en ruta detectado):** "
            f"{a['r06_diversion_detected_count']} detecciones",
            f"- **D03 (Verdes dejando zona ALTA sin amb. ≤20m):** "
            f"{a['d03_green_uncovered_warnings']} alertas",
            f"- **D05 (TAM en 02 habiendo TAB disponible):** {a['d05_tam_on_02_warnings']} alertas",
            f"- **D06 (TAB priorizada en 07 con traslado probable):** "
            f"{a['d06_transfer_tab_activations']} activaciones",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablación comparativa y auditoría de reglas EMI.")
    parser.add_argument("--json", type=Path, help="Guardar salida JSON.")
    args = parser.parse_args()

    with SessionLocal() as db:
        out = run_ablation(db)

    print(render_ablation_markdown(out))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
