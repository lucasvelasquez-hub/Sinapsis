"""Carga incremental del dataset real de Grupo EMI en raw.* sin romper la auditoría.

- Tablas de referencia (`response_targets`, `service_rules`, `zone_travel_times`,
  `traffic_factors`, `care_centers`, `zones`, `bases`): upsert o reemplazo limpio.
- `raw.units` y los servicios históricos de `raw.services`: upsert por clave.
  Lo que desaparece del dataset se borra si nada lo referencia; si lo referencian
  recomendaciones o decisiones (registro de auditoría), se conserva.
- Las solicitudes simuladas (`is_synthetic`) nunca se tocan.
- La sesión de simulación se resincroniza con el dataset cargado.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, NamedTuple

import pandas as pd
from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.decision import DispatchDecision, Recommendation, RecommendationCandidate
from app.models.raw import (
    RawBase,
    RawCareCenter,
    RawResponseTarget,
    RawService,
    RawServiceRule,
    RawTrafficFactor,
    RawUnit,
    RawZone,
    RawZoneTravelTime,
)
from app.services.simulation_service import resync_simulation_session

# psycopg admite como mucho 65535 parámetros por sentencia (~24 por servicio).
UPSERT_BATCH = 1000


class DatasetFrames(NamedTuple):
    """DataFrames normalizados del dataset EMI listos para persistencia."""

    targets: pd.DataFrame
    rules: pd.DataFrame
    bases: pd.DataFrame
    units: pd.DataFrame
    zones: pd.DataFrame
    travel_times: pd.DataFrame
    traffic_factors: pd.DataFrame
    care_centers: pd.DataFrame
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


def _upsert(db: Session, model: type, rows: list[dict[str, Any]], key: str | list[str]) -> None:
    keys = [key] if isinstance(key, str) else list(key)
    for batch in _batches(rows):
        stmt = insert(model).values(batch)
        updates = {c: stmt.excluded[c] for c in batch[0] if c not in keys}
        changed = or_(*(model.__table__.c[c].is_distinct_from(stmt.excluded[c]) for c in updates))
        db.execute(stmt.on_conflict_do_update(index_elements=keys, set_=updates, where=changed))


def _dt_or_none(val: Any) -> Any:
    if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
        return None
    return val.to_pydatetime() if hasattr(val, "to_pydatetime") else val


def _float_or_none(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    return float(val)


def _str_or_none(val: Any) -> str | None:
    if val is None or pd.isna(val):
        return None
    return str(val)


def _replace_reference_tables(db: Session, frames: DatasetFrames) -> None:
    db.execute(delete(RawResponseTarget))
    db.execute(delete(RawServiceRule))
    db.execute(delete(RawTrafficFactor))
    db.execute(delete(RawCareCenter))

    db.add_all(
        RawResponseTarget(
            urgency_level=str(r.urgency_level),
            description=str(r.description),
            manchester_scale=str(r.manchester_scale),
            target_response_min=int(r.target_response_min),
        )
        for r in frames.targets.itertuples(index=False)
    )
    db.add_all(
        RawServiceRule(
            urgency_level=str(r.urgency_level),
            unit_type=str(r.unit_type),
            eligible=bool(r.eligible),
            compatibility_level=str(r.compatibility_level),
            compatibility_rank=int(r.compatibility_rank),
        )
        for r in frames.rules.itertuples(index=False)
    )
    db.add_all(
        RawTrafficFactor(
            day_type=str(r.day_type),
            hour_start=int(r.hour_start),
            hour_end=int(r.hour_end),
            factor=float(r.factor),
        )
        for r in frames.traffic_factors.itertuples(index=False)
    )
    db.add_all(
        RawCareCenter(
            center_id=str(r.center_id),
            name=str(r.name),
            zone_id=str(r.zone_id),
            complexity_level=str(r.complexity_level),
        )
        for r in frames.care_centers.itertuples(index=False)
    )
    db.flush()

    _upsert(
        db,
        RawBase,
        [
            {
                "base_id": str(r.base_id),
                "name": str(r.name),
                "municipality": str(r.municipality),
                "zone_id": str(r.zone_id),
                "lat": float(r.lat),
                "lon": float(r.lon),
            }
            for r in frames.bases.itertuples(index=False)
        ],
        key="base_id",
    )
    _upsert(
        db,
        RawZone,
        [
            {
                "zone_id": str(r.zone_id),
                "municipality": str(r.municipality),
                "comuna": str(r.comuna),
                "lat_centroid": float(r.lat_centroid),
                "lon_centroid": float(r.lon_centroid),
                "relative_demand": str(r.relative_demand),
            }
            for r in frames.zones.itertuples(index=False)
        ],
        key="zone_id",
    )
    _upsert(
        db,
        RawZoneTravelTime,
        [
            {
                "origin_zone_id": str(r.origin_zone_id),
                "destination_zone_id": str(r.destination_zone_id),
                "distance_km": float(r.distance_km),
                "valley_time_min": float(r.valley_time_min),
                "peak_time_min": float(r.peak_time_min),
            }
            for r in frames.travel_times.itertuples(index=False)
        ],
        key=["origin_zone_id", "destination_zone_id"],
    )


def _service_rows(services: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "service_id": str(r.service_id),
            "request_datetime": _dt_or_none(r.request_datetime),
            "dispatch_datetime": _dt_or_none(r.dispatch_datetime),
            "urgency_level": str(r.urgency_level),
            "manchester_scale": _str_or_none(r.manchester_scale),
            "service_type": str(r.service_type),
            "discriminator": _str_or_none(r.discriminator),
            "channel": _str_or_none(r.channel),
            "zone_id": str(r.zone_id),
            "lat_approx": _float_or_none(r.lat_approx),
            "lon_approx": _float_or_none(r.lon_approx),
            "assigned_unit_id": _str_or_none(r.assigned_unit_id),
            "origin_zone_id": _str_or_none(r.origin_zone_id),
            "distance_km": _float_or_none(r.distance_km),
            "assignment_datetime": _dt_or_none(r.assignment_datetime),
            "arrival_datetime": _dt_or_none(r.arrival_datetime),
            "closure_datetime": _dt_or_none(r.closure_datetime),
            "reported_response_min": _float_or_none(r.reported_response_min),
            "required_transfer": bool(r.required_transfer)
            if r.required_transfer is not None and not pd.isna(r.required_transfer)
            else None,
            "destination_center": _str_or_none(r.destination_center),
            "closure_state": _str_or_none(r.closure_state),
            "classifications_json": r.classifications_json,
            "assigned_units_json": r.assigned_units_json,
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
    _replace_reference_tables(db, frames)

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
                "cost_per_km": _float_or_none(r.cost_per_km),
                "cost_per_hour": _float_or_none(r.cost_per_hour),
                "active": bool(r.active),
                "observation": _str_or_none(r.observation),
            }
            for r in frames.units.itertuples(index=False)
        ],
        key="unit_id",
    )

    service_ids = [str(s) for s in frames.services["service_id"]]
    _upsert(db, RawService, _service_rows(frames.services), key="service_id")

    missing_services = (
        RawService.is_synthetic.is_(False),
        RawService.service_id.not_in(service_ids),
    )
    services_deleted = db.execute(
        delete(RawService).where(*missing_services, ~_service_referenced())
    ).rowcount
    services_kept = db.execute(select(RawService.service_id).where(*missing_services)).all()

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
