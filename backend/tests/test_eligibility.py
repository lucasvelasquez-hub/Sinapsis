"""Motivos de exclusión estructurados (explicabilidad)."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ExclusionCode
from app.models.raw import RawService
from app.schemas.dispatch import ExclusionReason
from app.services.eligibility_service import evaluate_eligibility
from app.services.simulation_service import (
    mark_unit_assigned_in_simulation,
    update_assignment_fields,
)


def test_every_exclusion_has_codes_aligned_with_reasons(db: Session) -> None:
    service = db.execute(
        select(RawService).where(RawService.urgency_level == "06").limit(1)
    ).scalar_one()

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


def _service_of_urgency(db: Session, urgency_level: str) -> RawService:
    return db.execute(
        select(RawService)
        .where(RawService.urgency_level == urgency_level)
        .order_by(RawService.request_datetime.desc())
        .limit(1)
    ).scalar_one()


def test_ineligible_rule_excludes_with_incompatible_type(db: Session) -> None:
    service = _service_of_urgency(db, "06")

    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)

    ambulances = [ex for ex in evaluation.excluded_units if ex.unit_type in ("TAM", "TAB")]
    assert len(ambulances) > 0
    assert all(ExclusionCode.INCOMPATIBLE_TYPE in ex.reason_codes for ex in ambulances)
    assert not any(u.unit_type in ("TAM", "TAB") for u in evaluation.eligible_units)


def test_eligible_units_carry_compatibility_ranks(db: Session) -> None:
    service = _service_of_urgency(db, "01")

    evaluation, ranks = evaluate_eligibility(db, service, service.request_datetime)

    assert evaluation.eligible_units
    assert set(ranks.values()).issubset({1, 2, 3})
    assert set(ranks) == {u.unit_id for u in evaluation.eligible_units}


def test_capacity_is_no_longer_an_exclusion(db: Session) -> None:
    service = _service_of_urgency(db, "01")

    evaluation, _ = evaluate_eligibility(db, service, service.request_datetime)

    assert all(
        ExclusionCode.INSUFFICIENT_CAPACITY not in ex.reason_codes
        for ex in evaluation.excluded_units
    )


def test_a_request_is_not_blocked_by_its_own_simulated_assignment(db: Session) -> None:
    """Al revisar una solicitud ya despachada, su unidad no aparece ocupada por ella misma;
    otra solicitud en el mismo instante sí la ve ocupada."""
    service = _service_of_urgency(db, "01")
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
        urgency_level="02",
        service_type="Dolor torácico",
        zone_id="Z-MED-01-01",
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


def _open(
    db: Session, service_id: str, urgency: str, when: datetime, **extra: object
) -> RawService:
    row = RawService(
        service_id=service_id,
        request_datetime=when,
        urgency_level=urgency,
        service_type="Dolor torácico",
        zone_id="Z-MED-01-01",
        is_synthetic=True,
        status=str(extra.pop("status", "PENDING")),
    )
    db.add(row)
    db.flush()
    return row


def test_r06_excludes_unit_already_on_scene(db: Session) -> None:
    when = datetime(2027, 2, 2, 12, 0)
    origin = _open(db, "R06-SCENE", "03", when, status="DISPATCHED")
    origin.arrival_datetime = when + timedelta(minutes=5)
    probe = _open(db, "R06-PROBE-01", "01", when)
    unit_id = evaluate_eligibility(db, probe, when)[0].eligible_units[0].unit_id
    origin.assigned_unit_id = unit_id
    mark_unit_assigned_in_simulation(db, unit_id, origin.service_id, when, 90, urgency_level="03")
    update_assignment_fields(db, unit_id, origin.service_id, state="EN_ATENCION")
    db.flush()

    evaluation, _ = evaluate_eligibility(db, probe, when)

    assert unit_id not in {unit.unit_id for unit in evaluation.eligible_units}


def test_r06_offers_unit_en_route_to_06(db: Session) -> None:
    when = datetime(2027, 2, 2, 15, 0)
    origin = _open(db, "R06-ROUTE", "06", when, status="DISPATCHED")
    probe = _open(db, "R06-PROBE-02", "01", when)
    unit_id = evaluate_eligibility(db, probe, when)[0].eligible_units[0].unit_id
    origin.assigned_unit_id = unit_id
    mark_unit_assigned_in_simulation(db, unit_id, origin.service_id, when, 90, urgency_level="06")
    db.flush()

    evaluation, _ = evaluate_eligibility(db, probe, when)
    offered = next(unit for unit in evaluation.eligible_units if unit.unit_id == unit_id)

    assert offered.diversion_of_service_id == origin.service_id
    assert any(factor.startswith("Regla R06:") for factor in getattr(offered, "rule_factors", []))
