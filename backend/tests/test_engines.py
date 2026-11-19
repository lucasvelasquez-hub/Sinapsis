from app.services.eligibility_service import shift_covers_hour
from app.services.scoring_service import (
    compute_mcdm_score,
    compute_raw_workload_index,
    normalize_min_max_0_100,
)


def test_normalize_min_max_0_100() -> None:
    assert normalize_min_max_0_100([]) == []
    assert normalize_min_max_0_100([10.0, 10.0]) == [0.0, 0.0]
    assert normalize_min_max_0_100([10.0, 20.0, 30.0]) == [0.0, 50.0, 100.0]


def test_compute_mcdm_score_default_weights() -> None:
    # J(j) = 0.8 * T(j) + 0.2 * L(j)
    assert compute_mcdm_score(0.0, 0.0) == 0.0
    assert compute_mcdm_score(100.0, 100.0) == 100.0
    assert compute_mcdm_score(50.0, 25.0, 0.80, 0.20) == 45.0


def test_compute_raw_workload_index() -> None:
    assert compute_raw_workload_index(2, 4, 6) == 0.5 * 2 + 0.3 * 4 + 0.2 * 6


def test_shift_covers_hour() -> None:
    assert shift_covers_hour("FULL_24H", 3) is True
    assert shift_covers_hour("MORNING", 8) is True
    assert shift_covers_hour("MORNING", 15) is False
    assert shift_covers_hour("AFTERNOON", 18) is True
    assert shift_covers_hour("NIGHT", 23) is True
    assert shift_covers_hour("NIGHT", 2) is True
    assert shift_covers_hour("NIGHT", 12) is False
