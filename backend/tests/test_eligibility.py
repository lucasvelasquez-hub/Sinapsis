"""Motivos de exclusión estructurados (explicabilidad)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ExclusionCode
from app.models.raw import RawService
from app.schemas.dispatch import ExclusionReason
from app.services.eligibility_service import evaluate_eligibility
from app.services.simulation_service import mark_unit_assigned_in_simulation


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


def _service_of_type(db: Session, service_type: str) -> RawService:
    return db.execute(
        select(RawService).where(RawService.service_type == service_type).limit(1)
    ).scalar_one()


def test_ineligible_rule_excludes_with_incompatible_type(db: Session) -> None:
    service = _service_of_type(db, "EVENTO_ESPECIAL")

    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)

    basicas = [ex for ex in evaluation.excluded_units if ex.unit_type == "BASICA"]
    assert len(basicas) == 15
    assert all(ExclusionCode.INCOMPATIBLE_TYPE in ex.reason_codes for ex in basicas)
    assert not any(u.unit_type == "BASICA" for u in evaluation.eligible_units)


def test_all_eligible_units_have_rank_one(db: Session) -> None:
    service = _service_of_type(db, "EMERGENCIA_MEDICA")

    evaluation, ranks = evaluate_eligibility(db, service, service.request_datetime)

    assert evaluation.eligible_units
    assert set(ranks.values()) == {1}
    assert set(ranks) == {u.unit_id for u in evaluation.eligible_units}


def test_capacity_is_no_longer_an_exclusion(db: Session) -> None:
    service = _service_of_type(db, "EMERGENCIA_MEDICA")

    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)

    assert all(
        ExclusionCode.INSUFFICIENT_CAPACITY not in ex.reason_codes
        for ex in evaluation.excluded_units
    )


def test_a_request_is_not_blocked_by_its_own_simulated_assignment(db: Session) -> None:
    """Al revisar una solicitud ya despachada, su unidad no aparece ocupada por ella misma;
    otra solicitud en el mismo instante sí la ve ocupada."""
    service = _service_of_type(db, "EMERGENCIA_MEDICA")
    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)
    unit_id = evaluation.eligible_units[0].unit_id
    mark_unit_assigned_in_simulation(
        db,
        unit_id=unit_id,
        service_id=service.service_id,
        start_dt=service.request_datetime,
        duration_min=60,
    )
    other = RawService(
        service_id="SIM-OTRA",
        request_datetime=service.request_datetime,
        urgency_level="ALTA",
        service_type="EMERGENCIA_MEDICA",
        zone_id="COMUNA_01",
        status="PENDING",
        is_synthetic=True,
    )
    db.add(other)
    db.flush()

    own, _ = evaluate_eligibility(db, service, service.request_datetime)
    theirs, _ = evaluate_eligibility(db, other, other.request_datetime)

    assert unit_id in {u.unit_id for u in own.eligible_units}
    busy = next(ex for ex in theirs.excluded_units if ex.unit_id == unit_id)
    assert ExclusionCode.BUSY_IN_SIMULATION in busy.reason_codes
