from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from app.models.core import AuditEvent


def record_audit_event(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None,
) -> AuditEvent:
    """Persist an immutable audit event in core.audit_events."""
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload or {},
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    return event
