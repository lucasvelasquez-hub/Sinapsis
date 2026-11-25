from app.domain.assignment_policy import (
    PolicyUnit,
    is_transfer_likely,
    rank_units,
)

D03 = "Regla D03: deja zona de demanda ALTA sin ambulancia <=20 min"


def _unit(
    unit_id: str,
    unit_type: str,
    arrival_min: float,
    *,
    cost: float = 100.0,
    workload: float = 0.0,
    leaves_alta_uncovered: bool = False,
) -> PolicyUnit:
    return PolicyUnit(
        unit_id=unit_id,
        unit_type=unit_type,
        arrival_min=arrival_min,
        cost=cost,
        workload=workload,
        leaves_alta_uncovered=leaves_alta_uncovered,
        diverted_from_service_id=None,
    )


def test_d01_faster_other_municipality_beats_slower_local() -> None:
    ranked = rank_units(
        "01",
        15,
        [
            _unit("lenta", "TAB", 20, cost=10),
            _unit("rapida", "TAB", 8, cost=900),
        ],
        transfer_likely=False,
    )
    assert [r.unit.unit_id for r in ranked] == ["rapida", "lenta"]
    assert not hasattr(ranked[0].unit, "zone_id")


def test_d02_cost_breaks_tie_inside_three_minutes() -> None:
    inside = rank_units(
        "01",
        15,
        [
            _unit("cara", "TAB", 10.0, cost=500),
            _unit("barata", "TAB", 12.9, cost=100),
        ],
        transfer_likely=False,
    )
    assert inside[0].unit.unit_id == "barata"

    outside = rank_units(
        "01",
        15,
        [
            _unit("cara", "TAB", 10.0, cost=500),
            _unit("barata", "TAB", 13.0, cost=100),
        ],
        transfer_likely=False,
    )
    assert outside[0].unit.unit_id == "cara"


def test_d05_tab_before_tam_inside_band_on_02() -> None:
    on_02 = rank_units(
        "02",
        20,
        [
            _unit("tam", "TAM", 11, cost=100),
            _unit("tab", "TAB", 12, cost=100),
        ],
        transfer_likely=False,
    )
    assert [r.unit.unit_id for r in on_02] == ["tab", "tam"]
    assert any(w.startswith("Regla D05:") for w in on_02[1].warnings)

    on_01 = rank_units(
        "01",
        15,
        [
            _unit("tam", "TAM", 11, cost=100),
            _unit("tab", "TAB", 12, cost=100),
        ],
        transfer_likely=False,
    )
    assert on_01[0].unit.unit_id == "tam"


def test_d04_workload_breaks_tie_after_cost() -> None:
    tied = rank_units(
        "03",
        90,
        [
            _unit("cargada", "VMD", 30, cost=100, workload=4),
            _unit("libre", "VMD", 30, cost=100, workload=1),
        ],
        transfer_likely=False,
    )
    assert tied[0].unit.unit_id == "libre"

    spread = rank_units(
        "03",
        90,
        [
            _unit("cargada", "VMD", 30, cost=100, workload=4),
            _unit("lejana", "VMD", 33, cost=10, workload=0),
        ],
        transfer_likely=False,
    )
    assert spread[0].unit.unit_id == "cargada"


def test_d06_tab_rises_when_07_meets_target() -> None:
    both_in = rank_units(
        "07",
        45,
        [
            _unit("vmd", "VMD", 20),
            _unit("tab", "TAB", 40),
        ],
        transfer_likely=True,
    )
    assert both_in[0].unit.unit_id == "tab"

    tab_late = rank_units(
        "07",
        45,
        [
            _unit("vmd", "VMD", 20),
            _unit("tab", "TAB", 50),
        ],
        transfer_likely=True,
    )
    assert tab_late[0].unit.unit_id == "vmd"

    no_transfer = rank_units(
        "07",
        45,
        [
            _unit("vmd", "VMD", 20),
            _unit("tab", "TAB", 40),
        ],
        transfer_likely=False,
    )
    assert no_transfer[0].unit.unit_id == "vmd"


def test_d03_demotes_last_alta_ambulance_on_green_only() -> None:
    green = rank_units(
        "03",
        90,
        [
            _unit("cubre", "VMD", 30, leaves_alta_uncovered=False),
            _unit("descubre", "VMD", 28, leaves_alta_uncovered=True),
        ],
        transfer_likely=False,
    )
    assert [r.unit.unit_id for r in green] == ["cubre", "descubre"]
    assert green[1].tier == 1

    red = rank_units(
        "01",
        15,
        [
            _unit("rapida", "TAB", 8, leaves_alta_uncovered=True),
            _unit("lenta", "TAB", 20, leaves_alta_uncovered=False),
        ],
        transfer_likely=False,
    )
    assert red[0].unit.unit_id == "rapida"
    assert D03 in red[0].warnings


def test_transfer_likely_vocabulary() -> None:
    assert is_transfer_likely("Caídas", None) is True
    assert is_transfer_likely("Heridas", None) is True
    assert is_transfer_likely(None, "Signos de deshidratación") is True
    assert is_transfer_likely("Diarrea y vómitos", "Náuseas") is False
