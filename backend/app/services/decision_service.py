import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, CoreDomainError, ResourceNotFoundError
from app.domain.assignment_policy import DESVIO_PREFIX
from app.domain.enums import ServiceStatus
from app.domain.temporal import utcnow
from app.models.decision import DispatchDecision, Recommendation, RecommendationCandidate
from app.models.raw import RawService, RawUnit
from app.schemas.dispatch import DecisionCreate, DecisionOut
from app.services.audit_service import record_audit_event
from app.services.eligibility_service import evaluate_eligibility
from app.services.simulation_service import (
    historical_median_request_to_closure_min,
    mark_unit_assigned_in_simulation,
    release_service_in_simulation,
)


def record_dispatch_decision(db: Session, payload: DecisionCreate) -> DecisionOut:
    """Record human dispatch decision, update service & simulation state, and log audit.

    Locks the service row first (then the simulation session): a concurrent decision on the
    same service waits and then sees it already decided (409) instead of failing on the
    unique constraint. Lock order service → session everywhere avoids deadlocks. An R06
    diversion locks both service rows in ascending id order before the session.
    """
    origin_id = _accepted_diversion_origin(db, payload)
    service, locked = _lock_services(db, payload.service_id, origin_id)

    if payload.assigned_unit_id:
        unit = db.get(RawUnit, payload.assigned_unit_id)
        if unit is None:
            raise ResourceNotFoundError("Unit", payload.assigned_unit_id)
    elif payload.accepted:
        raise CoreDomainError("assigned_unit_id is required when accepted=true.")

    if not payload.accepted and not payload.assigned_unit_id and not payload.rejection_reason:
        raise CoreDomainError("rejection_reason is required when rejecting all recommendations.")

    if service.status != ServiceStatus.PENDING:
        raise ConflictError(
            f"Service '{service.service_id}' already has status {service.status}.",
            code="SERVICE_ALREADY_DECIDED",
        )

    origin = _require_open_diversion(locked, origin_id, payload.assigned_unit_id)

    recommendation_score = _validated_recommendation_score(db, payload)
    eligibility_override = (
        _eligibility_override(db, service, payload.assigned_unit_id)
        if payload.assigned_unit_id
        else []
    )

    now_utc = utcnow()
    decision_id = str(uuid.uuid4())

    decision = DispatchDecision(
        decision_id=decision_id,
        service_id=payload.service_id,
        recommendation_id=payload.recommendation_id,
        recommended_unit_id=payload.recommended_unit_id,
        assigned_unit_id=payload.assigned_unit_id,
        recommendation_score=recommendation_score,
        accepted=payload.accepted,
        rejection_reason=payload.rejection_reason,
        eligibility_override=eligibility_override,
        dispatcher_id=payload.dispatcher_id,
        decision_datetime=now_utc,
    )
    db.add(decision)

    if origin is not None and payload.assigned_unit_id:
        release_service_in_simulation(db, payload.assigned_unit_id, origin.service_id)
        origin.assigned_unit_id = None
        origin.status = ServiceStatus.PENDING
        record_audit_event(
            db,
            event_type="DIVERSION_ACCEPTED",
            entity_type="service",
            entity_id=origin.service_id,
            payload={
                "origin_service_id": origin.service_id,
                "service_id": service.service_id,
                "assigned_unit_id": payload.assigned_unit_id,
                "dispatcher_id": payload.dispatcher_id,
            },
        )

    if payload.assigned_unit_id:
        service.assigned_unit_id = payload.assigned_unit_id
        service.status = ServiceStatus.DISPATCHED
        # The simulated occupation lives only in the simulation session: raw.services
        # keeps observed data (no invented duration or completion time).
        mark_unit_assigned_in_simulation(
            db,
            unit_id=payload.assigned_unit_id,
            service_id=service.service_id,
            start_dt=service.request_datetime,
            duration_min=historical_median_request_to_closure_min(db, service.service_type),
            urgency_level=service.urgency_level,
        )
    else:
        service.status = ServiceStatus.REJECTED

    record_audit_event(
        db,
        event_type="DISPATCH_DECISION_RECORDED",
        entity_type="decision",
        entity_id=decision_id,
        payload={
            "service_id": payload.service_id,
            "recommended_unit_id": payload.recommended_unit_id,
            "assigned_unit_id": payload.assigned_unit_id,
            "accepted": payload.accepted,
            "rejection_reason": payload.rejection_reason,
            "eligibility_override": eligibility_override,
            "dispatcher_id": payload.dispatcher_id,
        },
    )
    db.commit()
    db.refresh(decision)

    return DecisionOut.model_validate(decision)


def list_decisions(db: Session, limit: int = 50, offset: int = 0) -> list[DecisionOut]:
    rows = (
        db.execute(
            select(DispatchDecision)
            .order_by(DispatchDecision.decision_datetime.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [DecisionOut.model_validate(r) for r in rows]


def _validated_recommendation_score(db: Session, payload: DecisionCreate) -> float | None:
    """Check the decision against its recommendation and return the server-side score.

    The client never sets the score: it is read from the persisted candidate.
    """
    if payload.recommendation_id is None:
        if payload.recommended_unit_id is not None:
            raise CoreDomainError(
                "recommended_unit_id requires recommendation_id.",
                code="RECOMMENDATION_MISMATCH",
            )
        return None

    rec = db.get(Recommendation, payload.recommendation_id)
    if rec is None:
        raise ResourceNotFoundError("Recommendation", payload.recommendation_id)
    if rec.service_id != payload.service_id:
        raise CoreDomainError(
            f"Recommendation '{rec.recommendation_id}' belongs to service '{rec.service_id}'.",
            code="RECOMMENDATION_MISMATCH",
        )
    if payload.recommended_unit_id is None:
        return None

    candidate = db.execute(
        select(RecommendationCandidate).where(
            RecommendationCandidate.recommendation_id == rec.recommendation_id,
            RecommendationCandidate.unit_id == payload.recommended_unit_id,
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise CoreDomainError(
            f"Unit '{payload.recommended_unit_id}' is not a candidate of this recommendation.",
            code="RECOMMENDATION_MISMATCH",
        )
    return candidate.score


def _accepted_diversion_origin(db: Session, payload: DecisionCreate) -> str | None:
    """Service id tagged DESVIO: on the accepted candidate. Read before any lock."""
    if not payload.accepted or not payload.assigned_unit_id or payload.recommendation_id is None:
        return None
    candidate = db.execute(
        select(RecommendationCandidate).where(
            RecommendationCandidate.recommendation_id == payload.recommendation_id,
            RecommendationCandidate.unit_id == payload.assigned_unit_id,
        )
    ).scalar_one_or_none()
    if candidate is None:
        return None
    for factor in candidate.factors_json or []:
        if isinstance(factor, str) and factor.startswith(DESVIO_PREFIX):
            origin_id = factor.removeprefix(DESVIO_PREFIX)
            return origin_id or None
    return None


def _lock_services(
    db: Session, service_id: str, origin_id: str | None
) -> tuple[RawService, dict[str, RawService | None]]:
    """Lock the new service and, for R06, the origin, in ascending service-id order."""
    ids = [service_id]
    if origin_id and origin_id != service_id:
        ids.append(origin_id)
    locked: dict[str, RawService | None] = {}
    for sid in sorted(ids):
        row = db.get(RawService, sid, with_for_update=True, populate_existing=True)
        if sid == service_id and row is None:
            raise ResourceNotFoundError("Service request", service_id)
        locked[sid] = row
    service = locked[service_id]
    if service is None:
        raise ResourceNotFoundError("Service request", service_id)
    return service, locked


def _require_open_diversion(
    locked: dict[str, RawService | None],
    origin_id: str | None,
    unit_id: str | None,
) -> RawService | None:
    """409 before any write when the diverted service is no longer en route."""
    if origin_id is None:
        return None
    origin = locked.get(origin_id)
    still_en_route = (
        origin is not None
        and unit_id is not None
        and origin.status == ServiceStatus.DISPATCHED
        and origin.arrival_datetime is None
        and origin.assigned_unit_id == unit_id
    )
    if not still_en_route:
        raise ConflictError(
            "La móvil ya no va en ruta hacia el servicio que se iba a desviar.",
            code="DIVERSION_NOT_EN_ROUTE",
        )
    return origin


def _eligibility_override(db: Session, service: RawService, unit_id: str) -> list[str]:
    """Exclusion reasons of the assigned unit; empty when it is eligible.

    The dispatcher may assign an excluded unit (the final decision is human), but the
    override must be recorded with its reasons.
    """
    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)
    for excluded in evaluation.excluded_units:
        if excluded.unit_id == unit_id:
            return list(excluded.reasons)
    return []
