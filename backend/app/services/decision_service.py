import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, CoreDomainError, ResourceNotFoundError
from app.domain.enums import ServiceStatus
from app.domain.temporal import utcnow
from app.models.decision import DispatchDecision, Recommendation, RecommendationCandidate
from app.models.raw import RawService, RawUnit
from app.schemas.dispatch import DecisionCreate, DecisionOut
from app.services.audit_service import record_audit_event
from app.services.eligibility_service import evaluate_eligibility
from app.services.simulation_service import (
    historical_median_occupation_min,
    mark_unit_assigned_in_simulation,
)


def record_dispatch_decision(db: Session, payload: DecisionCreate) -> DecisionOut:
    """Record human dispatch decision, update service & simulation state, and log audit."""
    service = db.get(RawService, payload.service_id)
    if service is None:
        raise ResourceNotFoundError("Service request", payload.service_id)

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
            duration_min=historical_median_occupation_min(db, service.service_type),
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
