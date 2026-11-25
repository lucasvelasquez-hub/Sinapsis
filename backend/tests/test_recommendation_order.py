"""El orden del Top 3 sigue la política del documento 03, no el municipio."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.raw import RawService, RawZone, RawZoneTravelTime
from app.schemas.dispatch import EligibilityEvaluation, UnitStatusOut
from app.services.recommendation_service import retention_median_min, score_candidates


def _unit(unit_id: str, zone_id: str, unit_type: str = "TAB") -> UnitStatusOut:
    return UnitStatusOut(
        unit_id=unit_id,
        unit_type=unit_type,
        base_id="B-TEST",
        shift="TURNO_24H",
        capacity=1,
        cost_per_km=1000,
        cost_per_hour=1000,
        current_zone_id=zone_id,
        active=True,
        simulated_available=True,
        workload_4h=0,
        workload_8h=0,
        workload_12h=0,
    )


def _set_travel(db: Session, origin: str, destination: str, minutes: float, km: float) -> None:
    row = db.get(RawZoneTravelTime, {"origin_zone_id": origin, "destination_zone_id": destination})
    if row is None:
        db.add(
            RawZoneTravelTime(
                origin_zone_id=origin,
                destination_zone_id=destination,
                distance_km=km,
                valley_time_min=minutes,
                peak_time_min=minutes,
            )
        )
    else:
        row.valley_time_min = minutes
        row.peak_time_min = minutes
        row.distance_km = km


def test_same_municipality_does_not_beat_faster_unit(db: Session) -> None:
    service = db.execute(
        select(RawService).where(RawService.urgency_level == "01").limit(1)
    ).scalar_one()
    dest = db.get(RawZone, service.zone_id)
    assert dest is not None
    zones = db.execute(select(RawZone)).scalars().all()
    local = next(
        z for z in zones if z.municipality == dest.municipality and z.zone_id != dest.zone_id
    )
    far = next(z for z in zones if z.municipality != dest.municipality)
    _set_travel(db, local.zone_id, dest.zone_id, 40, 30)
    _set_travel(db, far.zone_id, dest.zone_id, 4, 3)
    db.flush()

    eligibility = EligibilityEvaluation(
        service_id=service.service_id,
        evaluation_datetime=service.request_datetime,
        eligible_units=[_unit("local", local.zone_id), _unit("lejos", far.zone_id)],
        excluded_units=[],
    )
    ranked = score_candidates(
        db, service, eligibility, {"local": 1, "lejos": 1}, 0.5, 0.2, 0.15, 0.15
    )

    assert ranked[0].unit.unit_id == "lejos"


def test_d06_recommends_tab_for_fall_within_target(db: Session) -> None:
    service = db.execute(
        select(RawService)
        .join(RawZone, RawZone.zone_id == RawService.zone_id)
        .where(RawService.urgency_level == "07", RawZone.relative_demand != "ALTA")
        .limit(1)
    ).scalar_one()
    service.service_type = "Caídas"
    service.discriminator = "Deformidad o dolor moderado en extremidad"
    zones = [
        z.zone_id
        for z in db.execute(select(RawZone)).scalars().all()
        if z.zone_id != service.zone_id
    ]
    vmd_zone, tab_zone = zones[0], zones[1]
    for zone in db.execute(select(RawZone)).scalars().all():
        if zone.relative_demand == "ALTA" and zone.zone_id != service.zone_id:
            _set_travel(db, tab_zone, zone.zone_id, 40, 30)
    _set_travel(db, vmd_zone, service.zone_id, 6, 4)
    _set_travel(db, tab_zone, service.zone_id, 12, 8)
    db.flush()

    vmd = _unit("vmd", vmd_zone, "VMD")
    tab = _unit("tab", tab_zone)
    eligibility = EligibilityEvaluation(
        service_id=service.service_id,
        evaluation_datetime=service.request_datetime,
        eligible_units=[vmd, tab],
        excluded_units=[],
    )
    ranked = score_candidates(db, service, eligibility, {"vmd": 1, "tab": 2}, 0.5, 0.2, 0.15, 0.15)

    assert ranked[0].unit.unit_id == "tab"
    assert any(w.startswith("Regla D06:") for w in ranked[0].warnings)


def test_d03_warning_does_not_drop_fastest_01(db: Session) -> None:
    service = db.execute(
        select(RawService).where(RawService.urgency_level == "01").limit(1)
    ).scalar_one()
    zones = db.execute(select(RawZone)).scalars().all()
    alta = next(z for z in zones if z.relative_demand == "ALTA" and z.zone_id != service.zone_id)
    others = [z.zone_id for z in zones if z.zone_id not in {service.zone_id, alta.zone_id}]
    fast_zone, slow_zone = others[0], others[1]
    _set_travel(db, fast_zone, service.zone_id, 4, 2)
    _set_travel(db, slow_zone, service.zone_id, 25, 18)
    _set_travel(db, fast_zone, alta.zone_id, 5, 3)
    for zone in zones:
        if zone.relative_demand == "ALTA":
            _set_travel(db, slow_zone, zone.zone_id, 40, 30)
    db.flush()

    eligibility = EligibilityEvaluation(
        service_id=service.service_id,
        evaluation_datetime=service.request_datetime,
        eligible_units=[_unit("rapida", fast_zone), _unit("lenta", slow_zone)],
        excluded_units=[],
    )
    ranked = score_candidates(
        db, service, eligibility, {"rapida": 1, "lenta": 1}, 0.5, 0.2, 0.15, 0.15
    )

    assert ranked[0].unit.unit_id == "rapida"
    assert any(w.startswith("Regla D03:") for w in ranked[0].warnings)


def test_d08_retention_is_per_center(db: Session) -> None:
    zone_id = db.execute(select(RawZone.zone_id).limit(1)).scalar_one()

    def add(service_id: str, center: str, minutes: int) -> None:
        start = datetime(2026, 4, 1, 10, 0)
        end = start + timedelta(minutes=minutes)
        db.add(
            RawService(
                service_id=service_id,
                request_datetime=datetime(2026, 4, 1, 9, 0),
                urgency_level="01",
                service_type="Dolor torácico",
                zone_id=zone_id,
                destination_center=center,
                required_transfer=True,
                assigned_units_json=[
                    {
                        "fecha_hora_llegada_destino": start.isoformat(),
                        "fecha_hora_liberacion": end.isoformat(),
                    }
                ],
                status="COMPLETED",
                is_synthetic=True,
            )
        )

    for i in range(5):
        add(f"RET-A-{i}", "CENTRO_A_TEST", 10)
        add(f"RET-B-{i}", "CENTRO_B_TEST", 40)
    for i in range(4):
        add(f"RET-C-{i}", "CENTRO_POCOS", 100)
    db.flush()

    center_a, text_a = retention_median_min(db, "CENTRO_A_TEST")
    center_b, _text_b = retention_median_min(db, "CENTRO_B_TEST")
    few, text_few = retention_median_min(db, "CENTRO_POCOS")
    global_med, _ = retention_median_min(db, None)

    assert center_a == 10
    assert center_b == 40
    assert "CENTRO_A_TEST" in text_a
    assert "PREDICHO" in text_a
    assert few == global_med
    assert "global" in text_few
