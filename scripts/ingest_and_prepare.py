"""Idempotent ingestion of data/raw/*.csv into PostgreSQL + feature engineering."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import delete

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.core import ScoringConfig, SimulationSession  # noqa: E402
from app.models.raw import RawResponseTarget, RawService, RawServiceRule, RawUnit  # noqa: E402
from app.services.feature_service import compute_chronological_features  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_dataset import load_services, read_csv, validate  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def main() -> None:
    problems = validate(RAW_DIR)
    if problems:
        raise SystemExit("Dataset inválido, no se ingiere:\n- " + "\n- ".join(problems))

    targets_df = read_csv(RAW_DIR, "response_targets.csv")
    rules_df = read_csv(RAW_DIR, "service_rules.csv")
    units_df = read_csv(RAW_DIR, "units.csv")
    services_df = load_services(RAW_DIR)

    with SessionLocal() as db:
        # Idempotente. Sin CASCADE: si hay decisiones o recomendaciones que referencian estos
        # servicios, el DELETE falla a propósito (las FK protegen la auditoría).
        db.execute(delete(RawService))
        db.execute(delete(RawUnit))
        db.execute(delete(RawServiceRule))
        db.execute(delete(RawResponseTarget))

        db.bulk_save_objects(
            [
                RawResponseTarget(
                    urgency_level=str(r.urgency_level),
                    target_response_min=int(r.target_response_minutes),
                )
                for r in targets_df.itertuples(index=False)
            ]
        )
        db.bulk_save_objects(
            [
                RawServiceRule(
                    service_type=str(r.service_type),
                    unit_type=str(r.unit_type),
                    eligible=str(r.eligible).lower() == "true",
                )
                for r in rules_df.itertuples(index=False)
            ]
        )
        db.bulk_save_objects(
            [
                RawUnit(
                    unit_id=str(r.unit_id),
                    unit_type=str(r.unit_type),
                    base_id=str(r.base_id),
                    shift=str(r.shift),
                    capacity=int(r.capacity),
                    cost_per_km=float(r.cost_per_km),
                    active=True,
                )
                for r in units_df.itertuples(index=False)
            ]
        )
        db.flush()
        db.bulk_save_objects(
            [
                RawService(
                    service_id=str(r.service_id),
                    request_datetime=r.request_datetime.to_pydatetime(),
                    assignment_datetime=r.assignment_datetime.to_pydatetime(),
                    arrival_datetime=r.arrival_datetime.to_pydatetime(),
                    closure_datetime=r.closure_datetime.to_pydatetime(),
                    urgency_level=str(r.urgency_level),
                    service_type=str(r.service_type),
                    zone_id=str(r.zone_id),
                    assigned_unit_id=str(r.assigned_unit_id),
                    status="COMPLETED",
                    is_synthetic=False,
                )
                for r in services_df.itertuples(index=False)
            ]
        )

        now_utc = datetime.now(UTC).replace(tzinfo=None)

        # Default MCDM Scoring Config
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
                    updated_at=now_utc,
                )
            )

        # Default Simulation Session positioned at the latest historical request timestamp
        latest_dt = services_df["request_datetime"].max().to_pydatetime()
        if db.get(SimulationSession, "default") is None:
            db.add(
                SimulationSession(
                    session_id="default",
                    current_sim_datetime=latest_dt,
                    active_assignments_json={},
                    created_at=now_utc,
                    updated_at=now_utc,
                )
            )

        db.commit()

        count = compute_chronological_features(db)
        print(
            f"Ingeridos {len(services_df)} servicios, {len(units_df)} unidades, "
            f"{len(rules_df)} reglas, {len(targets_df)} objetivos. {count} service_features."
        )

        # Export processed snapshot for ML reproducibility
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        # computed_at is excluded: the snapshot must be identical across runs (reproducible).
        features_df = pd.read_sql(
            "SELECT * FROM analytics.service_features ORDER BY service_id", db.bind
        ).drop(columns=["computed_at"])
        features_df.to_csv(PROCESSED_DIR / "service_features.csv", index=False)
        print(f"Exported {len(features_df)} rows to {PROCESSED_DIR / 'service_features.csv'}")


if __name__ == "__main__":
    main()
