"""Reglas de dominio puras y consistencia entre entrenamiento y servicio."""

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.enums import UrgencyLevel
from app.domain.temporal import shift_covers_hour, temporal_context, window_counts
from app.ml.features import FEATURE_COLUMNS, build_feature_frame

REF = datetime(2026, 10, 30, 12, 0)  # viernes


@pytest.mark.parametrize(
    ("dt", "is_weekend", "is_peak"),
    [
        (datetime(2026, 10, 30, 7, 0), False, True),
        (datetime(2026, 10, 30, 10, 59), False, True),
        (datetime(2026, 10, 30, 11, 0), False, False),
        (datetime(2026, 10, 31, 17, 0), True, True),
        (datetime(2026, 11, 1, 21, 0), True, False),
    ],
)
def test_temporal_context_flags(dt: datetime, is_weekend: bool, is_peak: bool) -> None:
    ctx = temporal_context(dt)

    assert (ctx.hour_of_day, ctx.day_of_week) == (dt.hour, dt.weekday())
    assert ctx.is_weekend is is_weekend
    assert ctx.is_peak_hour is is_peak


def test_window_counts_only_strictly_before_ref() -> None:
    stamps = [
        datetime(2026, 10, 29, 23, 59),  # >12h: fuera
        datetime(2026, 10, 30, 0, 0),  # justo 12h: dentro
        datetime(2026, 10, 30, 5, 0),  # 7h
        datetime(2026, 10, 30, 9, 0),  # 3h
        REF,  # el propio instante: fuera (sin fuga)
    ]

    # (4h, 8h, 12h)
    assert window_counts(stamps, REF) == (1, 2, 3)


@pytest.mark.parametrize(
    ("shift", "hour", "covered"),
    [
        ("TURNO_DIA", 5, False),
        ("TURNO_DIA", 6, True),
        ("TURNO_DIA", 17, True),
        ("TURNO_DIA", 18, False),
        ("TURNO_NOCHE", 17, False),
        ("TURNO_NOCHE", 18, True),
        ("TURNO_NOCHE", 0, True),
        ("TURNO_NOCHE", 5, True),
        ("TURNO_NOCHE", 6, False),
        ("TURNO_24H", 12, True),
        ("TURNO_DESCONOCIDO", 12, False),
    ],
)
def test_shift_covers_hour_new_shifts(shift: str, hour: int, covered: bool) -> None:
    assert shift_covers_hour(shift, hour) is covered


def test_every_hour_is_covered_by_exactly_one_12h_shift() -> None:
    for hour in range(24):
        assert shift_covers_hour("TURNO_DIA", hour) != shift_covers_hour("TURNO_NOCHE", hour)


def test_urgency_levels_match_dataset() -> None:
    assert [u.value for u in UrgencyLevel] == ["CRITICA", "ALTA", "MEDIA", "BAJA"]


def test_feature_row_uses_base_id_without_same_zone() -> None:
    frame = build_feature_frame(
        [
            {
                "request_datetime": datetime(2026, 10, 31, 8, 0),
                "urgency_level": "ALTA",
                "service_type": "EMERGENCIA_MEDICA",
                "zone_id": "COMUNA_01",
                "unit_type": "BASICA",
                "base_id": "BASE-01",
                "shift": "TURNO_DIA",
                "capacity": 2,
            }
        ]
    )

    assert list(frame.columns) == FEATURE_COLUMNS
    assert "same_zone" not in frame.columns and "base_zone_id" not in frame.columns
    row = frame.iloc[0]
    assert row.base_id == "BASE-01"
    assert (row.is_weekend, row.is_peak_hour) == (1, 1)


def test_build_feature_frame_matches_persisted_features(db: Session) -> None:
    """Las features de servicio deben coincidir con las de entrenamiento (sin desfase)."""
    rows = (
        db.execute(
            text(
                """
                SELECT s.request_datetime, s.urgency_level, s.service_type, s.zone_id,
                       u.unit_type, u.base_id, u.shift, u.capacity,
                       f.hour_of_day, f.day_of_week, f.is_weekend, f.is_peak_hour
                FROM raw.services s
                JOIN raw.units u ON s.assigned_unit_id = u.unit_id
                JOIN analytics.service_features f ON f.service_id = s.service_id
                ORDER BY s.request_datetime
                LIMIT 500
                """
            )
        )
        .mappings()
        .all()
    )
    assert rows, "dataset local vacío: ejecutar scripts/ingest_and_prepare.py"

    frame = build_feature_frame([dict(r) for r in rows])

    for row, (_, feat) in zip(rows, frame.iterrows(), strict=True):
        assert feat.hour_of_day == row["hour_of_day"]
        assert feat.day_of_week == row["day_of_week"]
        assert feat.is_weekend == int(row["is_weekend"])
        assert feat.is_peak_hour == int(row["is_peak_hour"])
