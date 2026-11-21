"""Carga incremental del dataset: recargar sin romper la auditoría."""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.decision import RecommendationCandidate
from app.models.raw import RawService, RawServiceRule, RawUnit
from app.schemas.dispatch import SimulateRequestCreate
from app.services.ingestion_service import DatasetFrames, load_dataset
from app.services.recommendation_service import evaluate_recommendations
from app.services.request_service import create_synthetic_request
from app.services.simulation_service import (
    get_or_create_simulation_session,
    mark_unit_assigned_in_simulation,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from validate_dataset import RAW_DIR, load_emi_frames  # noqa: E402


@pytest.fixture(scope="module")
def frames() -> DatasetFrames:
    raw = load_emi_frames(RAW_DIR)
    return DatasetFrames(
        targets=raw["targets"],
        rules=raw["rules"],
        bases=raw["bases"],
        units=raw["units"],
        zones=raw["zones"],
        travel_times=raw["travel_times"],
        traffic_factors=raw["traffic_factors"],
        care_centers=raw["care_centers"],
        services=raw["services"],
    )


def _historical_count(db: Session) -> int:
    return db.execute(
        select(func.count()).select_from(RawService).where(RawService.is_synthetic.is_(False))
    ).scalar_one()


def _without_services(frames: DatasetFrames, ids: set[str]) -> DatasetFrames:
    return frames._replace(services=frames.services[~frames.services["service_id"].isin(ids)])


def test_reload_same_dataset_keeps_everything(db: Session, frames: DatasetFrames) -> None:
    report = load_dataset(db, frames)

    assert _historical_count(db) == 10402
    assert db.execute(select(func.count()).select_from(RawUnit)).scalar_one() == 26
    assert report.services_deleted == 0
    assert report.services_kept_referenced == 0
    assert report.units_deleted == report.units_deactivated == 0


def test_reload_deletes_unreferenced_service_missing_from_csv(
    db: Session, frames: DatasetFrames
) -> None:
    report = load_dataset(db, _without_services(frames, {"SRV-000001"}))

    assert db.get(RawService, "SRV-000001") is None
    assert report.services_deleted == 1


def test_reload_keeps_referenced_service_missing_from_csv(
    db: Session, frames: DatasetFrames
) -> None:
    evaluate_recommendations(db, "SRV-000002")  # deja una recomendación que referencia el servicio

    report = load_dataset(db, _without_services(frames, {"SRV-000002"}))

    kept = db.get(RawService, "SRV-000002")
    assert kept is not None and kept.is_synthetic is False
    assert report.services_kept_referenced == 1
    assert report.services_deleted == 0


def test_reload_never_touches_synthetic_requests(db: Session, frames: DatasetFrames) -> None:
    created = create_synthetic_request(
        db,
        SimulateRequestCreate(
            urgency_level="02", service_type="Dolor torácico", zone_id="Z-MED-01-01"
        ),
    )

    load_dataset(db, frames)

    assert db.get(RawService, created.service_id) is not None


def _drop_unit(frames: DatasetFrames, unit_id: str) -> DatasetFrames:
    return frames._replace(
        units=frames.units[frames.units["unit_id"] != unit_id],
        services=frames.services[frames.services["assigned_unit_id"] != unit_id],
    )


def test_reload_deactivates_referenced_unit_missing_from_csv(
    db: Session, frames: DatasetFrames
) -> None:
    rec = evaluate_recommendations(db, "SRV-000003")
    unit_id = rec.candidates[0].unit_id

    report = load_dataset(db, _drop_unit(frames, unit_id))

    unit = db.get(RawUnit, unit_id)
    assert unit is not None and unit.active is False
    assert report.units_deactivated == 1


def test_reload_deletes_unreferenced_unit_missing_from_csv(
    db: Session, frames: DatasetFrames
) -> None:
    referenced = set(db.execute(select(RecommendationCandidate.unit_id)).scalars())
    unit_id = next(u for u in frames.units["unit_id"] if u not in referenced)

    report = load_dataset(db, _drop_unit(frames, unit_id))

    assert db.get(RawUnit, unit_id) is None
    assert report.units_deleted == 1


def test_reload_replaces_rules(db: Session, frames: DatasetFrames) -> None:
    rules = frames.rules.copy()
    rules["eligible"] = True

    load_dataset(db, frames._replace(rules=rules))

    rule = db.get(RawServiceRule, ("06", "TAM"))
    assert rule is not None and rule.eligible is True


def test_reload_resyncs_simulation(db: Session, frames: DatasetFrames) -> None:
    mark_unit_assigned_in_simulation(db, "MOV-001", "X-1", datetime(2026, 10, 29, 23, 0), 30)
    sim = get_or_create_simulation_session(db)
    sim.active_assignments_json = {**sim.active_assignments_json, "UNIT-OLD": []}
    sim.current_sim_datetime = datetime(2020, 1, 1)
    db.flush()

    load_dataset(db, frames)

    db.refresh(sim)
    latest = db.execute(select(func.max(RawService.request_datetime))).scalar_one()
    assert sim.current_sim_datetime == latest
    assert "MOV-001" in sim.active_assignments_json
    assert "UNIT-OLD" not in sim.active_assignments_json


def _row_version(db: Session, table: str, key: str, value: str) -> str:
    return db.execute(
        text(f"SELECT xmin::text FROM {table} WHERE {key} = :v"), {"v": value}
    ).scalar_one()


def test_reload_does_not_rewrite_unchanged_rows(db: Session, frames: DatasetFrames) -> None:
    """Sin cambios en el CSV no se reescribe (ni se bloquea) ninguna fila de unidades/servicios."""
    before = (
        _row_version(db, "raw.services", "service_id", "SRV-000010"),
        _row_version(db, "raw.units", "unit_id", "MOV-001"),
    )

    load_dataset(db, frames)

    after = (
        _row_version(db, "raw.services", "service_id", "SRV-000010"),
        _row_version(db, "raw.units", "unit_id", "MOV-001"),
    )
    assert after == before


def test_reload_updates_changed_rows(db: Session, frames: DatasetFrames) -> None:
    services = frames.services.copy()
    services.loc[services["service_id"] == "SRV-000010", "zone_id"] = "Z-MED-01-02"

    load_dataset(db, frames._replace(services=services))

    assert db.get(RawService, "SRV-000010").zone_id == "Z-MED-01-02"
