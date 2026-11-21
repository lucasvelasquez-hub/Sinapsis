"""Carga (incremental) del dataset real de Grupo EMI en PostgreSQL + feature engineering."""

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
from validate_dataset import load_emi_frames, validate  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def main() -> None:
    problems = validate(RAW_DIR)
    if problems:
        raise SystemExit("Dataset inválido, no se ingiere:\n- " + "\n- ".join(problems))

    raw_frames = load_emi_frames(RAW_DIR)
    frames = DatasetFrames(
        targets=raw_frames["targets"],
        rules=raw_frames["rules"],
        bases=raw_frames["bases"],
        units=raw_frames["units"],
        zones=raw_frames["zones"],
        travel_times=raw_frames["travel_times"],
        traffic_factors=raw_frames["traffic_factors"],
        care_centers=raw_frames["care_centers"],
        services=raw_frames["services"],
    )

    with SessionLocal() as db:
        report = load_dataset(db, frames)

        cfg = db.get(ScoringConfig, "default")
        if cfg is None:
            db.add(
                ScoringConfig(
                    config_id="default",
                    weight_time=0.50,
                    weight_workload=0.20,
                    weight_cost=0.15,
                    weight_coverage=0.15,
                    cost_enabled=True,
                    coverage_enabled=True,
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
        elif not cfg.cost_enabled or not cfg.coverage_enabled:
            cfg.weight_time = 0.50
            cfg.weight_workload = 0.20
            cfg.weight_cost = 0.15
            cfg.weight_coverage = 0.15
            cfg.cost_enabled = True
            cfg.coverage_enabled = True
            cfg.updated_at = datetime.now(UTC).replace(tzinfo=None)

        db.commit()

        count = compute_chronological_features(db)
        print(
            f"Servicios: {report.services_upserted} cargados, {report.services_deleted} borrados, "
            f"{report.services_kept_referenced} conservados por auditoría. "
            f"Unidades: {report.units_upserted} cargadas, {report.units_deleted} borradas, "
            f"{report.units_deactivated} inactivadas por auditoría. "
            f"{len(frames.zones)} zonas, {len(frames.travel_times)} pares O-D. "
            f"{count} service_features."
        )

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
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
