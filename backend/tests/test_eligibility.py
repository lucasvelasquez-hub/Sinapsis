"""Motivos de exclusión estructurados (explicabilidad)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ExclusionCode
from app.models.raw import RawService
from app.schemas.dispatch import ExclusionReason
from app.services.eligibility_service import evaluate_eligibility


def test_every_exclusion_has_codes_aligned_with_reasons(db: Session) -> None:
    service = db.execute(select(RawService).limit(1)).scalar_one()

    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)

    assert evaluation.excluded_units
    for ex in evaluation.excluded_units:
        assert ex.reason_codes
        assert [r.split(":")[0] for r in ex.reasons] == list(ex.reason_codes)


def test_exclusion_reason_parses_legacy_json_without_codes() -> None:
    legacy = {
        "unit_id": "U-1",
        "unit_code": "AMB-1",
        "unit_type": "BLS",
        "reasons": ["OUT_OF_SHIFT: Turno NIGHT no cubre las 10:00"],
    }

    ex = ExclusionReason.model_validate(legacy)

    assert ex.reason_codes == [ExclusionCode.OUT_OF_SHIFT]
