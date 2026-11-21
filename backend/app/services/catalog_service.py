"""Vocabularios del dataset, leídos de raw.* (una sola fuente para API, front y validación)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import CoreDomainError
from app.models.raw import RawResponseTarget, RawService, RawUnit, RawZone
from app.schemas.catalog import CatalogOut, UrgencyOut


class UnknownCatalogValueError(CoreDomainError):
    def __init__(self, field: str, value: str) -> None:
        super().__init__(
            message=f"{field} '{value}' no existe en el catálogo del dataset.",
            status_code=422,
            code="VALIDATION_ERROR",
        )


def _distinct(db: Session, column) -> list[str]:
    return list(db.execute(select(column).distinct().order_by(column)).scalars())


def get_catalog(db: Session) -> CatalogOut:
    targets = db.execute(
        select(RawResponseTarget).order_by(RawResponseTarget.target_response_min)
    ).scalars()
    zones = _distinct(db, RawZone.zone_id) or _distinct(db, RawService.zone_id)
    pairs = db.execute(
        select(RawService.urgency_level, RawService.service_type)
        .where(RawService.manchester_scale.is_not(None))
        .distinct()
        .order_by(RawService.urgency_level, RawService.service_type)
    ).all()
    by_urg: dict[str, list[str]] = {}
    all_types: set[str] = set()
    for urg, st in pairs:
        by_urg.setdefault(urg, []).append(st)
        all_types.add(st)
    service_types = sorted(all_types) if all_types else _distinct(db, RawService.service_type)
    return CatalogOut(
        urgencies=[
            UrgencyOut(
                code=t.urgency_level,
                description=t.description,
                manchester_scale=t.manchester_scale,
                target_response_min=t.target_response_min,
            )
            for t in targets
        ],
        service_types=service_types,
        service_types_by_urgency=by_urg,
        zones=zones,
        unit_types=_distinct(db, RawUnit.unit_type),
        shifts=_distinct(db, RawUnit.shift),
    )


def ensure_known_service_values(db: Session, service_type: str, zone_id: str) -> None:
    """Rechaza (422) un motivo de consulta o una zona que el dataset no conoce."""
    known_type = db.execute(
        select(RawService.service_type).where(RawService.service_type == service_type).limit(1)
    ).first()
    if known_type is None:
        raise UnknownCatalogValueError("service_type", service_type)
    known_zone = db.execute(
        select(RawZone.zone_id).where(RawZone.zone_id == zone_id).limit(1)
    ).first()
    if known_zone is None:
        known_zone = db.execute(
            select(RawService.zone_id).where(RawService.zone_id == zone_id).limit(1)
        ).first()
    if known_zone is None:
        raise UnknownCatalogValueError("zone_id", zone_id)
