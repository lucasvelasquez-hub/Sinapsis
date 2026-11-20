"""Validación del dataset sintético mínimo de data/raw/.

- `validate(raw_dir)` devuelve los problemas bloqueantes (lista vacía = válido). La ingesta lo
  llama y aborta si hay alguno.
- `findings(raw_dir)` devuelve hallazgos de calidad no bloqueantes (se documentan, no se corrigen).
- `main()` imprime ambos y regenera docs/decisions/data_quality_report.md.

Uso (desde backend/): uv run python ../scripts/validate_dataset.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
REPORT_PATH = ROOT_DIR / "docs" / "decisions" / "data_quality_report.md"

TIMESTAMPS = ["request_datetime", "assignment_datetime", "arrival_datetime", "closure_datetime"]
COLUMNS: dict[str, list[str]] = {
    "services.csv": [
        "service_id",
        *TIMESTAMPS,
        "urgency_level",
        "service_type",
        "zone_id",
        "assigned_unit_id",
    ],
    "units.csv": ["unit_id", "unit_type", "base_id", "shift", "capacity", "cost_per_km"],
    "service_rules.csv": ["service_type", "unit_type", "eligible"],
    "response_targets.csv": ["urgency_level", "target_response_minutes"],
}
URGENCIES = {"CRITICA", "ALTA", "MEDIA", "BAJA"}
SHIFTS = {"TURNO_24H", "TURNO_DIA", "TURNO_NOCHE"}
DAY_HOURS = range(6, 18)  # TURNO_DIA [06, 18); TURNO_NOCHE es el complemento


def read_csv(raw_dir: Path, name: str) -> pd.DataFrame:
    """Los CSV del dataset llevan BOM: utf-8-sig."""
    return pd.read_csv(raw_dir / name, encoding="utf-8-sig")


def _as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().eq("true")


def load_services(raw_dir: Path) -> pd.DataFrame:
    services = read_csv(raw_dir, "services.csv")
    for col in TIMESTAMPS:
        # El CSV trae nanosegundos; Postgres guarda microsegundos.
        services[col] = pd.to_datetime(services[col]).dt.floor("us")
    return services


def validate(raw_dir: Path = RAW_DIR) -> list[str]:
    problems: list[str] = []
    frames: dict[str, pd.DataFrame] = {}
    for name, cols in COLUMNS.items():
        if not (raw_dir / name).exists():
            problems.append(f"{name}: no existe")
            continue
        df = read_csv(raw_dir, name)
        missing = [c for c in cols if c not in df.columns]
        if missing:
            problems.append(f"{name}: faltan columnas {missing}")
            continue
        nulls = int(df[cols].isna().sum().sum())
        if nulls:
            problems.append(f"{name}: {nulls} valores nulos")
        frames[name] = df
    if len(frames) < len(COLUMNS):
        return problems

    services = load_services(raw_dir)
    units = frames["units.csv"]
    rules = frames["service_rules.csv"]

    for name, key in [
        ("services.csv", ["service_id"]),
        ("units.csv", ["unit_id"]),
        ("service_rules.csv", ["service_type", "unit_type"]),
        ("response_targets.csv", ["urgency_level"]),
    ]:
        dups = int(frames[name].duplicated(subset=key).sum())
        if dups:
            problems.append(f"{name}: {dups} claves duplicadas {key}")

    bad_urgency = set(services["urgency_level"]) - URGENCIES
    if bad_urgency:
        problems.append(f"services.csv: urgencias desconocidas {sorted(bad_urgency)}")
    missing_targets = URGENCIES - set(frames["response_targets.csv"]["urgency_level"])
    if missing_targets:
        problems.append(f"response_targets.csv: faltan urgencias {sorted(missing_targets)}")
    bad_shift = set(units["shift"]) - SHIFTS
    if bad_shift:
        problems.append(f"units.csv: turnos desconocidos {sorted(bad_shift)}")

    orphans = set(services["assigned_unit_id"]) - set(units["unit_id"])
    if orphans:
        problems.append(f"services.csv: unidades inexistentes {sorted(orphans)}")

    ordered = (
        (services["request_datetime"] <= services["assignment_datetime"])
        & (services["assignment_datetime"] <= services["arrival_datetime"])
        & (services["arrival_datetime"] <= services["closure_datetime"])
    )
    if not ordered.all():
        problems.append(f"services.csv: {int((~ordered).sum())} servicios con orden temporal roto")

    assigned = services.merge(
        units[["unit_id", "unit_type"]], left_on="assigned_unit_id", right_on="unit_id"
    ).merge(
        rules.assign(eligible=_as_bool(rules["eligible"])),
        on=["service_type", "unit_type"],
        how="left",
    )
    ineligible = int((assigned["eligible"] != True).sum())  # noqa: E712 — NaN = sin regla
    if ineligible:
        problems.append(f"services.csv: {ineligible} asignaciones a un par no elegible")

    return problems


def findings(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    services = load_services(raw_dir)
    units = read_csv(raw_dir, "units.csv")
    merged = services.merge(units, left_on="assigned_unit_id", right_on="unit_id")
    hour = merged["assignment_datetime"].dt.hour

    night_in_day = merged[(merged["shift"] == "TURNO_NOCHE") & hour.isin(DAY_HOURS)]
    day_in_night = merged[(merged["shift"] == "TURNO_DIA") & ~hour.isin(DAY_HOURS)]

    by_unit = services.sort_values(["assigned_unit_id", "assignment_datetime"])
    prev_close = by_unit.groupby("assigned_unit_id")["closure_datetime"].shift()
    gap_min = (by_unit["assignment_datetime"] - prev_close).dt.total_seconds() / 60

    return {
        "services": len(services),
        "units": len(units),
        "zones": int(services["zone_id"].nunique()),
        "request_range": (
            str(services["request_datetime"].min()),
            str(services["request_datetime"].max()),
        ),
        "night_shift_daytime_assignments": len(night_in_day),
        "night_shift_daytime_days": sorted(
            night_in_day["assignment_datetime"].dt.strftime("%Y-%m-%d").unique().tolist()
        ),
        "day_shift_nighttime_assignments": len(day_in_night),
        "overlaps": int((gap_min < 0).sum()),
        "min_gap_between_services_min": round(float(gap_min.min()), 2),
    }


def _report(problems: list[str], found: dict[str, Any]) -> str:
    status = "VÁLIDO" if not problems else "CON PROBLEMAS BLOQUEANTES"
    lines = [
        "# Informe de calidad de datos — dataset sintético mínimo",
        "",
        "Generado por `scripts/validate_dataset.py`. Fuente: `data/raw/` (inmutable).",
        "",
        f"## Estado: {status}",
        "",
    ]
    lines += [f"- {p}" for p in problems] or [
        "Sin problemas bloqueantes: columnas, nulos, claves,"
        " vocabularios, orden temporal y pares elegibles OK."
    ]
    lines += [
        "",
        "## Hallazgos (no bloqueantes, no se corrigen)",
        "",
        f"- Servicios: {found['services']} · unidades: {found['units']} · zonas: {found['zones']}",
        f"- Rango de solicitudes: {found['request_range'][0]} → {found['request_range'][1]}",
        f"- Asignaciones de unidades TURNO_NOCHE en horario de día [06,18): "
        f"{found['night_shift_daytime_assignments']} "
        f"({', '.join(found['night_shift_daytime_days'])})."
        " Son picos de demanda; la elegibilidad aplica el turno a solicitudes nuevas.",
        f"- Asignaciones de unidades TURNO_DIA fuera de [06,18): "
        f"{found['day_shift_nighttime_assignments']}",
        f"- Solapes (asignación antes del cierre del servicio anterior de la misma unidad): "
        f"{found['overlaps']}",
        f"- Hueco mínimo entre cierre y siguiente asignación: "
        f"{found['min_gap_between_services_min']} min",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    problems = validate(RAW_DIR)
    found = findings(RAW_DIR) if not problems else {}
    for p in problems:
        print(f"PROBLEMA: {p}")
    if found:
        for k, v in found.items():
            print(f"{k}: {v}")
        REPORT_PATH.write_text(_report(problems, found), encoding="utf-8")
        print(f"Informe: {REPORT_PATH}")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
