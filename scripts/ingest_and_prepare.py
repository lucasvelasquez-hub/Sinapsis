"""Carga (incremental) de data/raw/*.csv en PostgreSQL + feature engineering.

Recargable aunque existan recomendaciones y decisiones: ver app/services/ingestion_service.py.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.core import ScoringConfig  # noqa: E402
from app.services.feature_service import compute_chronological_features  # noqa: E402
from app.services.ingestion_service import DatasetFrames, load_dataset  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_dataset import load_services, read_csv, validate  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def main() -> None:
    problems = validate(RAW_DIR)
    if problems:
        raise SystemExit("Dataset inválido, no se ingiere:\n- " + "\n- ".join(problems))

    frames = DatasetFrames(
        targets=read_csv(RAW_DIR, "response_targets.csv"),
        rules=read_csv(RAW_DIR, "service_rules.csv"),
        units=read_csv(RAW_DIR, "units.csv"),
        services=load_services(RAW_DIR),
    )

    with SessionLocal() as db:
        report = load_dataset(db, frames)

        if db.get(ScoringConfig, "default") is None:
            db.add(
                ScoringConfig(
                    config_id="default",
                    weight_time=0.80,
                    weight_workload=0.20,
                    weight_cost=0.00,
                    weight_coverage=0.00,
                    cost_enabled=False,
                    coverage_enabled=False,
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )

        db.commit()

        count = compute_chronological_features(db)
        print(
            f"Servicios: {report.services_upserted} cargados, {report.services_deleted} borrados, "
            f"{report.services_kept_referenced} conservados por auditoría. "
            f"Unidades: {report.units_upserted} cargadas, {report.units_deleted} borradas, "
            f"{report.units_deactivated} inactivadas por auditoría. "
            f"{len(frames.rules)} reglas, {len(frames.targets)} objetivos. "
            f"{count} service_features."
        )

        # Export processed snapshot for ML reproducibility
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        # computed_at is excluded: the snapshot must be identical across runs (reproducible).
        # Solo el histórico del dataset: las solicitudes simuladas no forman parte del snapshot.
        features_df = pd.read_sql(
            "SELECT f.* FROM analytics.service_features f"
            " JOIN raw.services s ON s.service_id = f.service_id"
            " WHERE NOT s.is_synthetic ORDER BY f.service_id",
            db.bind,
        ).drop(columns=["computed_at"])
        features_df.to_csv(PROCESSED_DIR / "service_features.csv", index=False)
        print(f"Exported {len(features_df)} rows to {PROCESSED_DIR / 'service_features.csv'}")


if __name__ == "__main__":
    main()
