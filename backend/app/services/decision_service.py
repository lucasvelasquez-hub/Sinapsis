import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import CoreDomainError, ResourceNotFoundError
from app.models.decision import DispatchDecision
from app.models.raw import RawService, RawUnit
from app.schemas.dispatch import DecisionCreate, DecisionOut
from app.services.audit_service import record_audit_event
from app.services.simulation_service import mark_unit_assigned_in_simulation


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

    now_utc = datetime.now(UTC).replace(tzinfo=None)
    decision_id = str(uuid.uuid4())

    decision = DispatchDecision(
        decision_id=decision_id,
        service_id=payload.service_id,
        recommendation_id=payload.recommendation_id,
        recommended_unit_id=payload.recommended_unit_id,
        assigned_unit_id=payload.assigned_unit_id,
        recommendation_score=payload.recommendation_score,
        accepted=payload.accepted,
        rejection_reason=payload.rejection_reason,
        decision_datetime=now_utc,
    )
    db.add(decision)

    if payload.assigned_unit_id:
        service.assigned_unit_id = payload.assigned_unit_id
        service.status = "DISPATCHED"
        est_duration = 45.0
        service.service_duration_min = est_duration
        service.completion_datetime = service.request_datetime + timedelta(minutes=est_duration)
        mark_unit_assigned_in_simulation(
            db,
            unit_id=payload.assigned_unit_id,
            service_id=service.service_id,
            start_dt=service.request_datetime,
            duration_min=est_duration,
        )
    else:
        service.status = "REJECTED"

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
        },
    )
    db.commit()
    db.refresh(decision)

    return DecisionOut(
        decision_id=decision.decision_id,
        service_id=decision.service_id,
        recommendation_id=decision.recommendation_id,
        recommended_unit_id=decision.recommended_unit_id,
        assigned_unit_id=decision.assigned_unit_id,
        recommendation_score=decision.recommendation_score,
        accepted=decision.accepted,
        rejection_reason=decision.rejection_reason,
        decision_datetime=decision.decision_datetime,
    )


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
    return [
        DecisionOut(
            decision_id=r.decision_id,
            service_id=r.service_id,
            recommendation_id=r.recommendation_id,
            recommended_unit_id=r.recommended_unit_id,
            assigned_unit_id=r.assigned_unit_id,
            recommendation_score=r.recommendation_score,
            accepted=r.accepted,
            rejection_reason=r.rejection_reason,
            decision_datetime=r.decision_datetime,
        )
        for r in rows
    ]
