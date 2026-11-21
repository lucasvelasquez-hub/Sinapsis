"""Validación del dataset real de Grupo EMI en data/raw/ + informe de calidad."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
REPORT_PATH = ROOT_DIR / "docs" / "decisions" / "data_quality_report.md"

REQUIRED_FILES = (
    "01_servicios_historicos.json",
    "02_moviles_y_bases.json",
    "05_zonas_y_tiempos.xlsx",
    "06_escenarios_referencia.xlsx",
    "07_indicadores.xlsx",
)

EMI_TARGETS: list[dict] = [
    {
        "urgency_level": "01",
        "description": "EMERGENCIA - 15 MIN",
        "manchester_scale": "ROJO",
        "target_response_min": 15,
    },
    {
        "urgency_level": "02",
        "description": "URGENCIA - 20 MIN",
        "manchester_scale": "NARANJA",
        "target_response_min": 20,
    },
    {
        "urgency_level": "07",
        "description": "PRIORIZADO",
        "manchester_scale": "AMARILLO",
        "target_response_min": 45,
    },
    {
        "urgency_level": "03",
        "description": "CONSULTA",
        "manchester_scale": "VERDE",
        "target_response_min": 90,
    },
    {
        "urgency_level": "06",
        "description": "CONSULTA BANAL",
        "manchester_scale": "AZUL",
        "target_response_min": 180,
    },
]

# Matriz de compatibilidad (doc 03, sección 4)
EMI_RULES: list[dict] = [
    # 01 - Emergencia
    {"urgency_level": "01", "unit_type": "TAM", "eligible": True, "compatibility_level": "PREFERIDA", "compatibility_rank": 1},
    {"urgency_level": "01", "unit_type": "TAB", "eligible": True, "compatibility_level": "PERMITIDA", "compatibility_rank": 2},
    {"urgency_level": "01", "unit_type": "VMD", "eligible": True, "compatibility_level": "SOLO_ESTABILIZACION", "compatibility_rank": 3},
    # 02 - Urgencia
    {"urgency_level": "02", "unit_type": "TAM", "eligible": True, "compatibility_level": "PERMITIDA", "compatibility_rank": 2},
    {"urgency_level": "02", "unit_type": "TAB", "eligible": True, "compatibility_level": "PREFERIDA", "compatibility_rank": 1},
    {"urgency_level": "02", "unit_type": "VMD", "eligible": True, "compatibility_level": "SOLO_ESTABILIZACION", "compatibility_rank": 3},
    # 07 - Priorizado
    {"urgency_level": "07", "unit_type": "TAM", "eligible": True, "compatibility_level": "NO_RECOMENDADA", "compatibility_rank": 4},
    {"urgency_level": "07", "unit_type": "TAB", "eligible": True, "compatibility_level": "PERMITIDA", "compatibility_rank": 2},
    {"urgency_level": "07", "unit_type": "VMD", "eligible": True, "compatibility_level": "PREFERIDA", "compatibility_rank": 1},
    # 03 - Consulta
    {"urgency_level": "03", "unit_type": "TAM", "eligible": False, "compatibility_level": "NO_PERMITIDA", "compatibility_rank": 5},
    {"urgency_level": "03", "unit_type": "TAB", "eligible": True, "compatibility_level": "NO_RECOMENDADA", "compatibility_rank": 4},
    {"urgency_level": "03", "unit_type": "VMD", "eligible": True, "compatibility_level": "PREFERIDA", "compatibility_rank": 1},
    # 06 - Consulta banal
    {"urgency_level": "06", "unit_type": "TAM", "eligible": False, "compatibility_level": "NO_PERMITIDA", "compatibility_rank": 5},
    {"urgency_level": "06", "unit_type": "TAB", "eligible": False, "compatibility_level": "NO_PERMITIDA", "compatibility_rank": 5},
    {"urgency_level": "06", "unit_type": "VMD", "eligible": True, "compatibility_level": "PREFERIDA", "compatibility_rank": 1},
]


def _parse_hour(hhmm: str) -> int:
    return int(str(hhmm).split(":", 1)[0])


def load_emi_frames(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Lee los insumos reales de Grupo EMI y devuelve DataFrames listos para validar/ingerir."""
    fleet_data = json.loads((raw_dir / "02_moviles_y_bases.json").read_text(encoding="utf-8"))
    bases_df = pd.DataFrame(fleet_data["bases"]).rename(
        columns={"id_base": "base_id", "nombre_base": "name", "municipio": "municipality", "id_zona": "zone_id"}
    )
    units_df = pd.DataFrame(fleet_data["moviles"]).rename(
        columns={
            "id_movil": "unit_id",
            "tipo_movil": "unit_type",
            "id_base": "base_id",
            "costo_km": "cost_per_km",
            "costo_hora": "cost_per_hour",
            "activo": "active",
            "observacion": "observation",
        }
    )
    units_df["shift"] = "TURNO_24H"
    units_df["capacity"] = 1

    wb = openpyxl.load_workbook(raw_dir / "05_zonas_y_tiempos.xlsx", read_only=True, data_only=True)
    zones_df = pd.DataFrame(
        list(wb["zonas"].iter_rows(min_row=2, values_only=True)),
        columns=["zone_id", "municipality", "comuna", "lat_centroid", "lon_centroid", "relative_demand"],
    ).dropna(subset=["zone_id"])
    travel_df = pd.DataFrame(
        list(wb["matriz_tiempos"].iter_rows(min_row=2, values_only=True)),
        columns=["origin_zone_id", "destination_zone_id", "distance_km", "valley_time_min", "peak_time_min"],
    ).dropna(subset=["origin_zone_id", "destination_zone_id"])
    traffic_raw = pd.DataFrame(
        list(wb["factor_trafico"].iter_rows(min_row=2, values_only=True)),
        columns=["day_type", "hora_inicio", "hora_fin", "factor"],
    ).dropna(subset=["day_type"])
    traffic_raw["hour_start"] = traffic_raw["hora_inicio"].map(_parse_hour)
    traffic_raw["hour_end"] = traffic_raw["hora_fin"].map(_parse_hour)
    traffic_df = traffic_raw[["day_type", "hour_start", "hour_end", "factor"]]
    centers_df = pd.DataFrame(
        list(wb["centros_atencion"].iter_rows(min_row=2, values_only=True)),
        columns=["center_id", "name", "zone_id", "complexity_level"],
    ).dropna(subset=["center_id"])
    wb.close()

    srv_raw = json.loads((raw_dir / "01_servicios_historicos.json").read_text(encoding="utf-8"))["servicios"]
    rows = []
    for s in srv_raw:
        clfs = s.get("clasificaciones") or []
        last_clf = clfs[-1] if clfs else {}
        moviles = s.get("moviles") or []
        primary = next((m for m in moviles if m.get("estado") == "COMPLETADO"), moviles[0] if moviles else None)
        rows.append(
            {
                "service_id": s["id_servicio"],
                "request_datetime": pd.to_datetime(s["fecha_hora_solicitud"]),
                "dispatch_datetime": pd.to_datetime(s["fecha_hora_paso_a_despacho"])
                if s.get("fecha_hora_paso_a_despacho")
                else None,
                "urgency_level": s["clasificacion_final"],
                "manchester_scale": last_clf.get("escala_manchester"),
                "service_type": last_clf.get("motivo_consulta") or "Consulta general",
                "discriminator": last_clf.get("discriminador"),
                "channel": s.get("canal"),
                "zone_id": s["id_zona"],
                "lat_approx": s.get("lat_aprox"),
                "lon_approx": s.get("lon_aprox"),
                "assigned_unit_id": primary["id_movil"] if primary else None,
                "origin_zone_id": primary.get("zona_origen_movil") if primary else None,
                "distance_km": primary.get("distancia_km") if primary else None,
                "assignment_datetime": pd.to_datetime(primary["fecha_hora_asignacion"])
                if primary and primary.get("fecha_hora_asignacion")
                else None,
                "arrival_datetime": pd.to_datetime(primary["fecha_hora_llegada"])
                if primary and primary.get("fecha_hora_llegada")
                else None,
                "closure_datetime": pd.to_datetime(s["fecha_hora_cierre"])
                if s.get("fecha_hora_cierre")
                else None,
                "reported_response_min": s.get("tiempo_respuesta_min"),
                "required_transfer": s.get("requirio_traslado"),
                "destination_center": s.get("destino"),
                "closure_state": s.get("estado_cierre"),
                "classifications_json": clfs,
                "assigned_units_json": moviles,
            }
        )
    services_df = pd.DataFrame(rows)

    return {
        "targets": pd.DataFrame(EMI_TARGETS),
        "rules": pd.DataFrame(EMI_RULES),
        "bases": bases_df,
        "units": units_df,
        "zones": zones_df,
        "travel_times": travel_df,
        "traffic_factors": traffic_df,
        "care_centers": centers_df,
        "services": services_df,
    }


def validate(raw_dir: Path = RAW_DIR) -> list[str]:
    problems: list[str] = []
    for fname in REQUIRED_FILES:
        if not (raw_dir / fname).exists():
            problems.append(f"Falta el archivo requerido: {fname}")
    if problems:
        return problems

    frames = load_emi_frames(raw_dir)
    services = frames["services"]
    units = frames["units"]
    bases = frames["bases"]
    zones = frames["zones"]
    travel = frames["travel_times"]

    if services["service_id"].duplicated().any():
        problems.append("service_id duplicado en 01_servicios_historicos.json")
    if units["unit_id"].duplicated().any():
        problems.append("unit_id duplicado en 02_moviles_y_bases.json")
    if bases["base_id"].duplicated().any():
        problems.append("base_id duplicado en 02_moviles_y_bases.json")
    if zones["zone_id"].duplicated().any():
        problems.append("zone_id duplicado en 05_zonas_y_tiempos.xlsx")

    known_urgencies = {t["urgency_level"] for t in EMI_TARGETS}
    bad_urgencies = set(services["urgency_level"]) - known_urgencies
    if bad_urgencies:
        problems.append(f"Clasificaciones EMI desconocidas: {sorted(bad_urgencies)}")

    known_bases = set(bases["base_id"])
    bad_bases = set(units["base_id"]) - known_bases
    if bad_bases:
        problems.append(f"Móviles con base_id desconocido: {sorted(bad_bases)}")

    known_zones = set(zones["zone_id"])
    bad_srv_zones = set(services["zone_id"]) - known_zones
    if bad_srv_zones:
        problems.append(f"Servicios con id_zona fuera del maestro de zonas: {sorted(bad_srv_zones)}")

    known_units = set(units["unit_id"])
    assigned_units = set(services["assigned_unit_id"].dropna())
    bad_units = assigned_units - known_units
    if bad_units:
        problems.append(f"Servicios con id_movil desconocido: {sorted(bad_units)}")

    if len(travel) == 0:
        problems.append("matriz_tiempos está vacía")

    return problems


def write_report(raw_dir: Path = RAW_DIR, report_path: Path = REPORT_PATH) -> None:
    frames = load_emi_frames(raw_dir)
    s = frames["services"]
    u = frames["units"]
    z = frames["zones"]
    t = frames["travel_times"]
    null_channel = int(s["channel"].isna().sum())
    null_arrival = int(s["arrival_datetime"].isna().sum())
    null_tr = int(s["reported_response_min"].isna().sum())

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"""# Reporte de Calidad de Datos — Dataset Grupo EMI (EstudIA)

- **Servicios históricos**: {len(s):,} ({s['request_datetime'].min()} → {s['request_datetime'].max()})
- **Flota**: {len(u)} móviles ({u['unit_type'].value_counts().to_dict()}) en {len(frames['bases'])} bases
- **Zonas y matriz O-D**: {len(z)} zonas, {len(t):,} pares origen-destino, {len(frames['care_centers'])} centros de atención
- **Nulos esperados (imperfecciones realistas del dataset)**:
  - `canal` nulo: {null_channel} ({null_channel / len(s):.2%})
  - `arrival_datetime` nulo (resueltos por teléfono, cancelados en ruta o ~2% sin registro): {null_arrival} ({null_arrival / len(s):.2%})
  - `tiempo_respuesta_min` nulo: {null_tr} ({null_tr / len(s):.2%})
- **Distribución por clasificación EMI**: {s['urgency_level'].value_counts().to_dict()}
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    issues = validate(RAW_DIR)
    if issues:
        raise SystemExit("Validación fallida:\n- " + "\n- ".join(issues))
    write_report(RAW_DIR, REPORT_PATH)
    print(f"Dataset EMI válido. Reporte escrito en {REPORT_PATH}")
