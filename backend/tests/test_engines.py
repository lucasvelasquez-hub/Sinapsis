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
    # J(j) = 0.50·T + 0.20·L + 0.15·C + 0.15·K
    assert compute_mcdm_score(0.0, 0.0, 0.0, 0.0) == 0.0
    assert compute_mcdm_score(100.0, 100.0, 100.0, 100.0) == 100.0
    assert (
        compute_mcdm_score(
            50.0,
            25.0,
            weight_time=0.80,
            weight_workload=0.20,
            weight_cost=0.0,
            weight_coverage=0.0,
        )
        == 45.0
    )


def test_compute_raw_workload_index() -> None:
    assert compute_raw_workload_index(2, 4, 6) == 0.5 * 2 + 0.3 * 4 + 0.2 * 6
