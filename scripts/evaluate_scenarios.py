"""Evaluación reproducible de CORE contra los 14 escenarios de referencia EMI.

Uso (desde backend/):
    DATABASE_URL=postgresql+psycopg://core_user:core_password@localhost:5433/core_db \\
      uv run python ../scripts/evaluate_scenarios.py \\
      --md ../docs/decisions/scenario_benchmark_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.raw import RawResponseTarget  # noqa: E402
from app.schemas.benchmarks import ScenarioRequestEvalOut  # noqa: E402
from app.services.benchmarks_service import get_kpis_overview, list_scenarios  # noqa: E402
from app.services.scenario_replay import replay_scenario  # noqa: E402

DEFAULT_TARGETS = {"01": 15, "02": 20, "07": 45, "03": 90, "06": 120}

DISCREPANCY_CATEGORIES = (
    "MATCH_EXACTO",
    "MATCH_TIPO_MEJOR_ETA",
    "MATCH_TIPO_PEOR_ETA",
    "DIFF_TIPO_MEJOR_ETA",
    "DIFF_TIPO_PEOR_ETA",
    "SIN_MOVIL",
)


def classify_discrepancy(item: ScenarioRequestEvalOut) -> str:
    if item.recommended_unit_id is None:
        return "SIN_MOVIL"
    if item.matches_reference_unit:
        return "MATCH_EXACTO"
    core_better_or_equal = (
        item.estimated_travel_min is None
        or item.reference_eta_min is None
        or item.estimated_travel_min <= item.reference_eta_min
    )
    if item.matches_reference_type:
        return "MATCH_TIPO_MEJOR_ETA" if core_better_or_equal else "MATCH_TIPO_PEOR_ETA"
    return "DIFF_TIPO_MEJOR_ETA" if core_better_or_equal else "DIFF_TIPO_PEOR_ETA"


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _pct_or_zero(hits: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * hits / total, 1)


def build_benchmark_report(db: Session) -> dict[str, Any]:
    targets = dict(DEFAULT_TARGETS)
    for row in db.execute(select(RawResponseTarget)).scalars():
        targets[row.urgency_level] = int(row.target_response_min)

    scenarios_out: list[dict[str, Any]] = []
    requests_out: list[dict[str, Any]] = []
    cat_counter: Counter[str] = Counter({k: 0 for k in DISCREPANCY_CATEGORIES})

    all_eta_core: list[float] = []
    all_eta_ref: list[float] = []
    all_cost_core: list[float] = []
    all_cost_ref: list[float] = []
    all_dist_core: list[float] = []
    all_dist_ref: list[float] = []
    tot_req = 0
    tot_unit_match = 0
    tot_type_match = 0
    tot_sla_core_hits = 0
    tot_sla_core_n = 0
    tot_sla_ref_hits = 0
    tot_sla_ref_n = 0

    for sc in list_scenarios():
        ev = replay_scenario(db, sc.id_escenario)
        sc_eta_core: list[float] = []
        sc_eta_ref: list[float] = []
        sc_cost_core: list[float] = []
        sc_cost_ref: list[float] = []
        sc_dist_core: list[float] = []
        sc_dist_ref: list[float] = []
        sc_sla_core_hits = 0
        sc_sla_core_n = 0
        sc_sla_ref_hits = 0
        sc_sla_ref_n = 0
        sc_unit_matches = 0
        sc_type_matches = 0

        for r in ev.results:
            tot_req += 1
            cat = classify_discrepancy(r)
            cat_counter[cat] += 1
            if r.matches_reference_unit:
                sc_unit_matches += 1
                tot_unit_match += 1
            if r.matches_reference_type:
                sc_type_matches += 1
                tot_type_match += 1

            tgt = targets.get(r.clasificacion_inicial, 30)
            sla_core: bool | None = None
            sla_ref: bool | None = None

            if r.estimated_travel_min is not None:
                val = float(r.estimated_travel_min)
                sc_eta_core.append(val)
                all_eta_core.append(val)
                sla_core = val <= tgt
                sc_sla_core_n += 1
                tot_sla_core_n += 1
                if sla_core:
                    sc_sla_core_hits += 1
                    tot_sla_core_hits += 1

            if r.reference_eta_min is not None:
                val_ref = float(r.reference_eta_min)
                sc_eta_ref.append(val_ref)
                all_eta_ref.append(val_ref)
                sla_ref = val_ref <= tgt
                sc_sla_ref_n += 1
                tot_sla_ref_n += 1
                if sla_ref:
                    sc_sla_ref_hits += 1
                    tot_sla_ref_hits += 1

            if r.estimated_cost is not None:
                sc_cost_core.append(float(r.estimated_cost))
                all_cost_core.append(float(r.estimated_cost))
            if r.reference_estimated_cost is not None:
                sc_cost_ref.append(float(r.reference_estimated_cost))
                all_cost_ref.append(float(r.reference_estimated_cost))
            if r.distance_km is not None:
                sc_dist_core.append(float(r.distance_km))
                all_dist_core.append(float(r.distance_km))
            if r.reference_distance_km is not None:
                sc_dist_ref.append(float(r.reference_distance_km))
                all_dist_ref.append(float(r.reference_distance_km))

            eta_delta = (
                round(float(r.estimated_travel_min) - float(r.reference_eta_min), 2)
                if r.estimated_travel_min is not None and r.reference_eta_min is not None
                else None
            )

            requests_out.append(
                {
                    "id_escenario": sc.id_escenario,
                    "nombre_escenario": sc.nombre,
                    "id_solicitud": r.id_solicitud,
                    "minuto_llegada": r.minuto_llegada,
                    "clasificacion_inicial": r.clasificacion_inicial,
                    "id_zona": r.id_zona,
                    "motivo_consulta": r.motivo_consulta,
                    "discriminador": r.discriminador,
                    "recommended_unit_id": r.recommended_unit_id,
                    "recommended_unit_type": r.recommended_unit_type,
                    "recommended_role": r.recommended_role,
                    "paired_unit_id": r.paired_unit_id,
                    "estimated_travel_min": r.estimated_travel_min,
                    "estimated_cost": r.estimated_cost,
                    "distance_km": r.distance_km,
                    "reference_unit_id": r.reference_unit_id,
                    "reference_unit_type": r.reference_unit_type,
                    "reference_role": r.reference_role,
                    "reference_eta_min": r.reference_eta_min,
                    "reference_estimated_cost": r.reference_estimated_cost,
                    "reference_distance_km": r.reference_distance_km,
                    "reference_justification": r.reference_justification,
                    "matches_reference_unit": r.matches_reference_unit,
                    "matches_reference_type": r.matches_reference_type,
                    "sla_target_min": tgt,
                    "sla_met_core": sla_core,
                    "sla_met_ref": sla_ref,
                    "eta_delta_min": eta_delta,
                    "category": cat,
                    "factors": list(r.factors),
                    "warnings": list(r.warnings),
                }
            )

        avg_core = _mean_or_none(sc_eta_core)
        avg_ref = _mean_or_none(sc_eta_ref)
        sc_delta = (
            round(avg_core - avg_ref, 2) if avg_core is not None and avg_ref is not None else None
        )
        n_sc = len(ev.results)
        scenarios_out.append(
            {
                "id_escenario": sc.id_escenario,
                "nombre": sc.nombre,
                "objetivo_aprendizaje": sc.objetivo_aprendizaje,
                "n_solicitudes": n_sc,
                "events_applied": ev.events_applied,
                "unit_matches": sc_unit_matches,
                "type_matches": sc_type_matches,
                "unit_match_rate": ev.unit_match_rate,
                "type_match_rate": ev.type_match_rate,
                "avg_eta_core_min": avg_core,
                "avg_eta_ref_min": avg_ref,
                "eta_delta_min": sc_delta,
                "sla_core_pct": _pct_or_zero(sc_sla_core_hits, sc_sla_core_n),
                "sla_ref_pct": _pct_or_zero(sc_sla_ref_hits, sc_sla_ref_n),
                "avg_cost_core": _mean_or_none(sc_cost_core),
                "avg_cost_ref": _mean_or_none(sc_cost_ref),
                "avg_dist_core_km": _mean_or_none(sc_dist_core),
                "avg_dist_ref_km": _mean_or_none(sc_dist_ref),
            }
        )

    avg_all_core = _mean_or_none(all_eta_core)
    avg_all_ref = _mean_or_none(all_eta_ref)
    all_delta = (
        round(avg_all_core - avg_all_ref, 2)
        if avg_all_core is not None and avg_all_ref is not None
        else None
    )

    kpis_overview = get_kpis_overview(db)
    kpis_out = [k.model_dump() for k in kpis_overview.kpis]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provenance": "SIMULADO",
        "totals": {
            "total_scenarios": len(scenarios_out),
            "total_requests": tot_req,
            "unit_matches": tot_unit_match,
            "type_matches": tot_type_match,
            "unit_match_rate": round(tot_unit_match / max(1, tot_req), 4),
            "type_match_rate": round(tot_type_match / max(1, tot_req), 4),
            "avg_eta_core_min": avg_all_core,
            "avg_eta_ref_min": avg_all_ref,
            "eta_delta_min": all_delta,
            "sla_core_pct": _pct_or_zero(tot_sla_core_hits, tot_sla_core_n),
            "sla_ref_pct": _pct_or_zero(tot_sla_ref_hits, tot_sla_ref_n),
            "avg_cost_core": _mean_or_none(all_cost_core),
            "avg_cost_ref": _mean_or_none(all_cost_ref),
            "avg_dist_core_km": _mean_or_none(all_dist_core),
            "avg_dist_ref_km": _mean_or_none(all_dist_ref),
            "discrepancy_counts": dict(cat_counter),
        },
        "scenarios": scenarios_out,
        "kpis": kpis_out,
        "requests": requests_out,
    }


def _fmt(val: float | None, suffix: str = "") -> str:
    if val is None:
        return "N/D"
    return f"{val:.1f}{suffix}"


def _fmt_cop(val: float | None) -> str:
    if val is None:
        return "N/D"
    return f"${val:,.0f}"


def render_markdown_report(report: dict[str, Any]) -> str:
    t = report["totals"]
    type_pct = t["type_match_rate"] * 100
    unit_pct = t["unit_match_rate"] * 100
    eta_core = _fmt(t["avg_eta_core_min"], " min")
    eta_ref = _fmt(t["avg_eta_ref_min"], " min")
    eta_delta = _fmt(t["eta_delta_min"], " min")
    dist_core = _fmt(t["avg_dist_core_km"], " km")
    dist_ref = _fmt(t["avg_dist_ref_km"], " km")
    cost_core = _fmt_cop(t["avg_cost_core"])
    cost_ref = _fmt_cop(t["avg_cost_ref"])

    tot_n = t["total_requests"]
    sla_c = t["sla_core_pct"]
    sla_r = t["sla_ref_pct"]

    lines: list[str] = [
        "# Reporte de Benchmark — 14 Escenarios de Referencia EMI",
        "",
        f"Generado: `{report['generated_at']}` · Procedencia replay: `{report['provenance']}`",
        "",
        "## Resumen Ejecutivo",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Escenarios evaluados | {t['total_scenarios']} |",
        f"| Solicitudes evaluadas | {tot_n} |",
        f"| Coincidencia Tipo de Móvil | {t['type_matches']}/{tot_n} ({type_pct:.1f}%) |",
        f"| Coincidencia Móvil Exacto | {t['unit_matches']}/{tot_n} ({unit_pct:.1f}%) |",
        f"| ETA promedio CORE vs. Ref. | {eta_core} vs. {eta_ref} (Δ {eta_delta}) |",
        f"| Cumplimiento SLA CORE vs. Ref. | {sla_c:.1f}% vs. {sla_r:.1f}% |",
        f"| Distancia promedio CORE vs. Ref. | {dist_core} vs. {dist_ref} |",
        f"| Costo promedio CORE vs. Ref. | {cost_core} vs. {cost_ref} |",
        "",
        "### Distribución de Comparaciones (58 solicitudes)",
        "",
        "| Categoría | Conteo | % |",
        "|---|---:|---:|",
    ]
    for cat in DISCREPANCY_CATEGORIES:
        cnt = t["discrepancy_counts"].get(cat, 0)
        pct = 100.0 * cnt / max(1, t["total_requests"])
        lines.append(f"| `{cat}` | {cnt} | {pct:.1f}% |")

    sc_header = (
        "| Escenario | Nombre | Sol. | Ev. | Match Tipo | Match Móvil "
        "| ETA CORE | ETA Ref | Δ ETA | SLA CORE | SLA Ref |"
    )
    lines.extend(
        [
            "",
            "## Resultados por Escenario",
            "",
            sc_header,
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for sc in report["scenarios"]:
        n_sc = sc["n_solicitudes"]
        tm_pct = sc["type_match_rate"] * 100
        um_pct = sc["unit_match_rate"] * 100
        lines.append(
            f"| `{sc['id_escenario']}` | {sc['nombre']} | {n_sc} | {sc['events_applied']} "
            f"| {sc['type_matches']}/{n_sc} ({tm_pct:.0f}%) "
            f"| {sc['unit_matches']}/{n_sc} ({um_pct:.0f}%) "
            f"| {_fmt(sc['avg_eta_core_min'])} | {_fmt(sc['avg_eta_ref_min'])} "
            f"| {_fmt(sc['eta_delta_min'])} "
            f"| {sc['sla_core_pct']:.0f}% | {sc['sla_ref_pct']:.0f}% |"
        )

    kpi_header = (
        "| KPI | Nombre | Meta | Línea Base "
        "| Observado DB (`OBSERVADO`) | Simulado 14 esc. (`SIMULADO`) |"
    )
    lines.extend(
        [
            "",
            "## 12 KPIs de Operación (`07_indicadores.xlsx`)",
            "",
            kpi_header,
            "|---|---|---|---|---|---|",
        ]
    )
    for k in report["kpis"]:
        lines.append(
            f"| `{k['id_kpi']}` | {k['nombre']} | {k['meta_referencia']} "
            f"| {k['linea_base_ficticia']} "
            f"| {k['valor_actual_db'] or '—'} | {k['valor_simulado'] or '—'} |"
        )

    disc_header = (
        "| Esc. | Solicitud | EMI | Zona | CORE | ETA CORE "
        "| Referencia | ETA Ref | Categoría | Justificación Despachador | Advertencias CORE |"
    )
    lines.extend(
        [
            "",
            "## Desglose de Discrepancias (No Match Exacto)",
            "",
            disc_header,
            "|---|---|---|---|---|---:|---|---:|---|---|---|",
        ]
    )
    for r in report["requests"]:
        if r["category"] == "MATCH_EXACTO":
            continue
        core_label = (
            f"{r['recommended_unit_id']} ({r['recommended_unit_type']})"
            if r["recommended_unit_id"]
            else "SIN_MOVIL"
        )
        if r.get("paired_unit_id"):
            core_label += f" + {r['paired_unit_id']}"
        ref_label = (
            f"{r['reference_unit_id']} ({r['reference_unit_type']})"
            if r["reference_unit_id"]
            else "—"
        )
        just = (r["reference_justification"] or "—").replace("|", "/").replace("\n", " ")
        warns = ("; ".join(r["warnings"]) if r["warnings"] else "—").replace("|", "/")
        lines.append(
            f"| `{r['id_escenario']}` | `{r['id_solicitud']}` "
            f"| {r['clasificacion_inicial']} | {r['id_zona']} "
            f"| {core_label} | {_fmt(r['estimated_travel_min'])} "
            f"| {ref_label} | {_fmt(r['reference_eta_min'])} "
            f"| `{r['category']}` | {just} | {warns} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalúa CORE contra los 14 escenarios de referencia EMI."
    )
    parser.add_argument("--json", type=Path, help="Ruta para guardar el reporte en JSON.")
    parser.add_argument("--md", type=Path, help="Ruta para guardar el reporte en Markdown.")
    args = parser.parse_args()

    with SessionLocal() as db:
        report = build_benchmark_report(db)

    t = report["totals"]
    print(
        f"CORE Benchmark (14 escenarios, {t['total_requests']} solicitudes) | "
        f"Tipo: {t['type_matches']}/{t['total_requests']} ({t['type_match_rate'] * 100:.1f}%) | "
        f"Móvil: {t['unit_matches']}/{t['total_requests']} ({t['unit_match_rate'] * 100:.1f}%) | "
        f"ETA CORE {_fmt(t['avg_eta_core_min'], 'm')} vs Ref {_fmt(t['avg_eta_ref_min'], 'm')} "
        f"(Δ {_fmt(t['eta_delta_min'], 'm')}) | "
        f"SLA CORE {t['sla_core_pct']:.1f}% vs Ref {t['sla_ref_pct']:.1f}%"
    )
    print("Categorías:", t["discrepancy_counts"])

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON guardado en {args.json}")

    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(render_markdown_report(report), encoding="utf-8")
        print(f"Markdown guardado en {args.md}")


if __name__ == "__main__":
    main()
