"""Carga incremental del dataset de data/raw en raw.* sin romper la auditoría.

- `raw.response_targets` y `raw.service_rules`: nadie los referencia, se reemplazan.
- `raw.units` y los servicios históricos de `raw.services`: upsert por clave. Lo que desaparece
  del CSV se borra si nada lo referencia; si lo referencian recomendaciones o decisiones
  (registro de auditoría), se conserva: el servicio tal cual, la unidad inactiva.
- Las solicitudes simuladas (`is_synthetic`) nunca se tocan.
- La sesión de simulación se resincroniza con el dataset cargado.

Solo hace flush: el llamador (scripts/ingest_and_prepare.py) decide el commit.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, NamedTuple

import pandas as pd
from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.decision import DispatchDecision, Recommendation, RecommendationCandidate
from app.models.raw import RawResponseTarget, RawService, RawServiceRule, RawUnit
from app.services.simulation_service import resync_simulation_session

# psycopg admite como mucho 65535 parámetros por sentencia (~11 por servicio).
UPSERT_BATCH = 2000


class DatasetFrames(NamedTuple):
    """CSV del dataset con sus nombres de columna de origen (services con fechas parseadas)."""

    targets: pd.DataFrame
    rules: pd.DataFrame
    units: pd.DataFrame
    services: pd.DataFrame


@dataclass(frozen=True)
class IngestReport:
    services_upserted: int
    services_deleted: int
    services_kept_referenced: int
    units_upserted: int
    units_deleted: int
    units_deactivated: int


def _batches(rows: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(rows), UPSERT_BATCH):
        yield rows[i : i + UPSERT_BATCH]


def _upsert(db: Session, model: type, rows: list[dict[str, Any]], key: str) -> None:
    for batch in _batches(rows):
        stmt = insert(model).values(batch)
        updates = {c: stmt.excluded[c] for c in batch[0] if c != key}
        # Solo las filas que cambian: una recarga sin cambios no reescribe ni bloquea filas
        # (ni deja filas muertas) mientras la app sigue leyendo y decidiendo.
        changed = or_(*(model.__table__.c[c].is_distinct_from(stmt.excluded[c]) for c in updates))
        db.execute(stmt.on_conflict_do_update(index_elements=[key], set_=updates, where=changed))


def _as_bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _replace_targets_and_rules(db: Session, frames: DatasetFrames) -> None:
    db.execute(delete(RawResponseTarget))
    db.execute(delete(RawServiceRule))
    db.add_all(
        RawResponseTarget(
            urgency_level=str(r.urgency_level), target_response_min=int(r.target_response_minutes)
        )
        for r in frames.targets.itertuples(index=False)
    )
    db.add_all(
        RawServiceRule(
            service_type=str(r.service_type),
            unit_type=str(r.unit_type),
            eligible=_as_bool(r.eligible),
        )
        for r in frames.rules.itertuples(index=False)
    )
    db.flush()


def _service_rows(services: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "service_id": str(r.service_id),
            "request_datetime": r.request_datetime.to_pydatetime(),
            "assignment_datetime": r.assignment_datetime.to_pydatetime(),
            "arrival_datetime": r.arrival_datetime.to_pydatetime(),
            "closure_datetime": r.closure_datetime.to_pydatetime(),
            "urgency_level": str(r.urgency_level),
            "service_type": str(r.service_type),
            "zone_id": str(r.zone_id),
            "assigned_unit_id": str(r.assigned_unit_id),
            "status": "COMPLETED",
            "is_synthetic": False,
        }
        for r in services.itertuples(index=False)
    ]


def _service_referenced():
    return or_(
        exists().where(Recommendation.service_id == RawService.service_id),
        exists().where(DispatchDecision.service_id == RawService.service_id),
    )


def _unit_referenced():
    return or_(
        exists().where(RawService.assigned_unit_id == RawUnit.unit_id),
        exists().where(RecommendationCandidate.unit_id == RawUnit.unit_id),
        exists().where(DispatchDecision.assigned_unit_id == RawUnit.unit_id),
        exists().where(DispatchDecision.recommended_unit_id == RawUnit.unit_id),
    )


def load_dataset(db: Session, frames: DatasetFrames) -> IngestReport:
    _replace_targets_and_rules(db, frames)

    unit_ids = [str(u) for u in frames.units["unit_id"]]
    _upsert(
        db,
        RawUnit,
        [
            {
                "unit_id": str(r.unit_id),
                "unit_type": str(r.unit_type),
                "base_id": str(r.base_id),
                "shift": str(r.shift),
                "capacity": int(r.capacity),
                "cost_per_km": float(r.cost_per_km),
                "active": True,
            }
            for r in frames.units.itertuples(index=False)
        ],
        key="unit_id",
    )

    service_ids = [str(s) for s in frames.services["service_id"]]
    _upsert(db, RawService, _service_rows(frames.services), key="service_id")

    # Históricos que ya no están en el CSV: fuera si nada los referencia; si no, se conservan.
    missing_services = (
        RawService.is_synthetic.is_(False),
        RawService.service_id.not_in(service_ids),
    )
    services_deleted = db.execute(
        delete(RawService).where(*missing_services, ~_service_referenced())
    ).rowcount
    services_kept = db.execute(select(RawService.service_id).where(*missing_services)).all()

    # Unidades que ya no están en el CSV: fuera si nada las referencia; si no, inactivas.
    missing_units = RawUnit.unit_id.not_in(unit_ids)
    units_deleted = db.execute(delete(RawUnit).where(missing_units, ~_unit_referenced())).rowcount
    units_deactivated = db.execute(
        update(RawUnit).where(missing_units).values(active=False)
    ).rowcount

    resync_simulation_session(db, unit_ids)
    db.flush()
    return IngestReport(
        services_upserted=len(service_ids),
        services_deleted=services_deleted,
        services_kept_referenced=len(services_kept),
        units_upserted=len(unit_ids),
        units_deleted=units_deleted,
        units_deactivated=units_deactivated,
    )
