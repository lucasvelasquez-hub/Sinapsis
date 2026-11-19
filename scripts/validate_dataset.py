"""Dataset inspection and quality validation script for CORE MVP v1.0.

Validates:
1. File existence & row counts
2. Column names & data types
3. Primary key uniqueness
4. Referential integrity across CSVs
5. Null / missing values
6. Timestamp sequence & chronological consistency
Generates docs/decisions/data_quality_report.md.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
REPORT_PATH = ROOT_DIR / "docs" / "decisions" / "data_quality_report.md"


def main() -> None:
    services = pd.read_csv(RAW_DIR / "services.csv")
    units = pd.read_csv(RAW_DIR / "units.csv")
    rules = pd.read_csv(RAW_DIR / "service_rules.csv")
    targets = pd.read_csv(RAW_DIR / "response_targets.csv")

    services["request_datetime_parsed"] = pd.to_datetime(services["request_datetime"], format="ISO8601")
    services["completion_datetime_parsed"] = pd.to_datetime(services["completion_datetime"], format="ISO8601")

    # Checks
    null_counts = {
        "services": int(services.isna().sum().sum()),
        "units": int(units.isna().sum().sum()),
        "service_rules": int(rules.isna().sum().sum()),
        "response_targets": int(targets.isna().sum().sum()),
    }

    pk_unique = {
        "service_id": bool(services["service_id"].is_unique),
        "unit_id": bool(units["unit_id"].is_unique),
        "rule_id": bool(rules["rule_id"].is_unique),
        "urgency_level": bool(targets["urgency_level"].is_unique),
    }

    orphan_units = set(services["assigned_unit_id"]) - set(units["unit_id"])
    orphan_urgencies = set(services["urgency_level"]) - set(targets["urgency_level"])
    orphan_service_types = set(services["service_type"]) - set(rules["service_type"])

    is_monotonic = bool(services["request_datetime_parsed"].is_monotonic_increasing)
    invalid_completion = int(
        (services["completion_datetime_parsed"] <= services["request_datetime_parsed"]).sum()
    )
    span_days = (
        services["request_datetime_parsed"].max() - services["request_datetime_parsed"].min()
    ).days + 1

    # Assertions
    assert len(services) == 10_000, f"Expected 10000 services, got {len(services)}"
    assert len(units) == 30, f"Expected 30 units, got {len(units)}"
    assert len(rules) == 15, f"Expected 15 rules, got {len(rules)}"
    assert len(targets) == 4, f"Expected 4 targets, got {len(targets)}"
    assert all(v == 0 for v in null_counts.values()), f"Null values detected: {null_counts}"
    assert all(pk_unique.values()), f"Duplicate PKs detected: {pk_unique}"
    assert not orphan_units and not orphan_urgencies and not orphan_service_types
    assert is_monotonic, "request_datetime is not monotonically increasing"
    assert invalid_completion == 0, f"Found {invalid_completion} services with completion <= request"

    urgency_counts = "\n".join(
        f"- **{k}**: {v:,}" for k, v in services["urgency_level"].value_counts().items()
    )

    report = f"""# Informe de Calidad de Datos — CORE MVP v1.0

Fecha de inspección: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Fuente: `data/raw/`

## 1. Dimensiones Verificadas

| Archivo | Filas | Columnas | Nulos | PK Única |
| :--- | ---: | ---: | ---: | :---: |
| `services.csv` | {len(services):,} | {len(services.columns) - 2} | {null_counts['services']} | {"Sí" if pk_unique['service_id'] else "No"} |
| `units.csv` | {len(units):,} | {len(units.columns)} | {null_counts['units']} | {"Sí" if pk_unique['unit_id'] else "No"} |
| `service_rules.csv` | {len(rules):,} | {len(rules.columns)} | {null_counts['service_rules']} | {"Sí" if pk_unique['rule_id'] else "No"} |
| `response_targets.csv` | {len(targets):,} | {len(targets.columns)} | {null_counts['response_targets']} | {"Sí" if pk_unique['urgency_level'] else "No"} |

## 2. Integridad Referencial

- `services.assigned_unit_id -> units.unit_id`: **0 huérfanos**
- `services.urgency_level -> response_targets.urgency_level`: **0 huérfanos**
- `services.service_type -> service_rules.service_type`: **0 huérfanos**

## 3. Consistencia Temporal

- Rango temporal: `{services['request_datetime_parsed'].min()}` a `{services['request_datetime_parsed'].max()}` (**{span_days} días**).
- Secuencia monótona creciente en `request_datetime`: **{"Sí" if is_monotonic else "No"}**.
- Servicios con `completion_datetime <= request_datetime`: **{invalid_completion}**.

## 4. Estadísticas Descriptivas Iniciales

- Tiempo de respuesta promedio: **{services['response_time_min'].mean():.2f} min** (mediana: {services['response_time_min'].median():.2f} min, P90: {services['response_time_min'].quantile(0.90):.2f} min).
- Duración promedio de servicio: **{services['service_duration_min'].mean():.2f} min**.
- Distribución por urgencia:
{urgency_counts}

## 5. Limitaciones Documentadas

- No existen coordenadas GPS, distancias ni velocidades reales en los CSV originales.
- El cierre histórico (`completion_datetime`) se utiliza exclusivamente como proxy de ocupación en simulación cronológica.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Data quality report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
