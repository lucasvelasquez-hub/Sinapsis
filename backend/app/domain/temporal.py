"""Temporal rules shared by features, prediction, eligibility and request context.

All operational datetimes are naive local time (dataset convention). Audit timestamps
(`created_at`, `decision_datetime`...) are naive UTC from `utcnow()`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

PEAK_HOUR_RANGES: tuple[tuple[int, int], ...] = ((7, 10), (17, 20))  # inclusive
WINDOW_HOURS: tuple[int, int, int] = (4, 8, 12)

SHIFT_HOURS: dict[str, tuple[int, int]] = {  # [start, end) — NIGHT wraps midnight
    "MORNING": (6, 14),
    "AFTERNOON": (14, 22),
    "NIGHT": (22, 6),
}


def utcnow() -> datetime:
    """Naive UTC now, the convention of every audit timestamp column."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class TemporalContext:
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    is_peak_hour: bool


def is_peak_hour(hour: int) -> bool:
    return any(start <= hour <= end for start, end in PEAK_HOUR_RANGES)


def temporal_context(dt: datetime) -> TemporalContext:
    dow = dt.weekday()
    return TemporalContext(
        hour_of_day=dt.hour,
        day_of_week=dow,
        is_weekend=dow >= 5,
        is_peak_hour=is_peak_hour(dt.hour),
    )


def window_counts(timestamps: Iterable[datetime], ref_dt: datetime) -> tuple[int, int, int]:
    """Events in the 4h/8h/12h windows *strictly before* ref_dt (no temporal leakage).

    A window of N hours includes events at exactly ref_dt - N hours.
    """
    cutoffs = [ref_dt - timedelta(hours=h) for h in WINDOW_HOURS]
    counts = [0, 0, 0]
    for ts in timestamps:
        if ts >= ref_dt:
            continue
        for i, cutoff in enumerate(cutoffs):
            if ts >= cutoff:
                counts[i] += 1
    return counts[0], counts[1], counts[2]


def shift_covers_hour(shift: str, hour: int) -> bool:
    """S(j, t): whether the unit's shift covers the request hour."""
    if shift == "FULL_24H":
        return True
    bounds = SHIFT_HOURS.get(shift)
    if bounds is None:
        return False
    start, end = bounds
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end
