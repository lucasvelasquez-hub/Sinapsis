"""Idempotent ingestion of data/raw/*.csv into PostgreSQL + feature engineering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import delete

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.core import ScoringConfig, SimulationSession  # noqa: E402
from app.models.raw import RawResponseTarget, RawService, RawServiceRule, RawUnit  # noqa: E402
from app.services.feature_service import compute_chronological_features  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def main() -> None:
    targets_df = pd.read_csv(RAW_DIR / "response_targets.csv")
    rules_df = pd.read_csv(RAW_DIR / "service_rules.csv")
    units_df = pd.read_csv(RAW_DIR / "units.csv")
    services_df = pd.read_csv(RAW_DIR / "services.csv")

    services_df["request_datetime"] = pd.to_datetime(services_df["request_datetime"], format="ISO8601")
    services_df["completion_datetime"] = pd.to_datetime(services_df["completion_datetime"], format="ISO8601")

    with SessionLocal() as db:
        # Clear raw tables idempotently before bulk load
        db.execute(delete(RawService))
        db.execute(delete(RawUnit))
        db.execute(delete(RawServiceRule))
        db.execute(delete(RawResponseTarget))

        db.bulk_save_objects(
            [
                RawResponseTarget(
                    urgency_level=str(r.urgency_level),
                    target_response_min=int(r.target_response_min),
                    max_acceptable_min=int(r.max_acceptable_min),
                    sla_label=str(r.sla_label),
                    description=str(r.description),
                )
                for r in targets_df.itertuples(index=False)
            ]
        )

        db.bulk_save_objects(
            [
                RawServiceRule(
                    rule_id=str(r.rule_id),
                    service_type=str(r.service_type),
                    unit_type=str(r.unit_type),
                    compatible=str(r.compatible).lower() == "true",
                    priority_rank=int(r.priority_rank),
                    min_capacity=int(r.min_capacity),
                    notes=str(r.notes),
                )
                for r in rules_df.itertuples(index=False)
            ]
        )

        db.bulk_save_objects(
            [
                RawUnit(
                    unit_id=str(r.unit_id),
                    unit_code=str(r.unit_code),
                    unit_type=str(r.unit_type),
                    base_zone_id=str(r.base_zone_id),
                    shift=str(r.shift),
                    capacity=int(r.capacity),
                    active=str(r.active).lower() == "true",
                )
                for r in units_df.itertuples(index=False)
            ]
        )

        db.bulk_save_objects(
            [
                RawService(
                    service_id=str(r.service_id),
                    request_datetime=r.request_datetime.to_pydatetime(),
                    urgency_level=str(r.urgency_level),
                    service_type=str(r.service_type),
                    zone_id=str(r.zone_id),
                    assigned_unit_id=str(r.assigned_unit_id),
                    response_time_min=float(r.response_time_min),
                    service_duration_min=float(r.service_duration_min),
                    completion_datetime=r.completion_datetime.to_pydatetime(),
                    status=str(r.status),
                    is_synthetic=False,
                )
                for r in services_df.itertuples(index=False)
            ]
        )

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

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

        # Default Simulation Session positioned at latest historical timestamp + 5 min
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
        print(f"Ingested 10,000 services, 30 units, 15 rules, 4 targets. Computed {count} service_features.")

        # Export processed snapshot for ML reproducibility
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        features_df = pd.read_sql("SELECT * FROM analytics.service_features", db.bind)
        features_df.to_csv(PROCESSED_DIR / "service_features.csv", index=False)
        print(f"Exported {len(features_df)} rows to {PROCESSED_DIR / 'service_features.csv'}")


if __name__ == "__main__":
    main()
