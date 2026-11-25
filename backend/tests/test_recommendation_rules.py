"""Tests unitarios puros de las reglas de negocio EMI en recommendation_service."""

from app.services.recommendation_service import (
    _d06_possible_transfer,
    _effective_weights,
    _proximity_tier,
)
from app.services.scoring_service import normalize_workload_0_100


def test_proximity_tier_prefers_same_and_adjacent_zones_regardless_of_municipality() -> None:
    # Misma zona -> tier 0
    assert _proximity_tier(True, 1.2, 4.0) == 0
    # Zona aledaña (p. ej. Poblado <-> Envigado a 1.8 km / 5 min) -> tier 0
    assert _proximity_tier(False, 1.8, 5.0) == 0
    # Zona intermedia (7.5 km / 16 min) -> tier 1
    assert _proximity_tier(False, 7.5, 16.0) == 1
    # Zona lejana (14 km / 32 min, p. ej. Popular <-> Poblado) -> tier 2
    assert _proximity_tier(False, 14.0, 32.0) == 2


def test_d06_detects_possible_transfer_motives() -> None:
    assert _d06_possible_transfer("Caídas") is True
    assert _d06_possible_transfer("Trauma craneal") is True
    assert _d06_possible_transfer("Dolor abdominal en adulto") is True
    assert _d06_possible_transfer("Problema de salud mental") is False


def test_workload_normalization_does_not_inflate_single_service_to_100() -> None:
    # 0 vs 1 servicio en 4h/8h/12h debe penalizar 25/100 (no 100/100)
    assert normalize_workload_0_100([0.0, 0.0, 1.0]) == [0.0, 0.0, 25.0]
    # A partir de 4 servicios de diferencia llega a 100
    assert normalize_workload_0_100([0.0, 4.0]) == [0.0, 100.0]
    # Igual carga -> todos 0
    assert normalize_workload_0_100([2.0, 2.0]) == [0.0, 0.0]


def test_traffic_scales_time_weight_continuously_and_preserves_unit_sum() -> None:
    # Valle / madrugada (1.0x): pesos intactos
    wt, wl, wc, wk, vital, adjusted = _effective_weights("07", 0.50, 0.20, 0.15, 0.15, 1.0)
    assert (wt, wl, wc, wk, vital, adjusted) == (0.50, 0.20, 0.15, 0.15, False, False)

    # Sábado mediodía (1.35x): ajuste intermedio progresivo (~0.61) y suma 1.0
    wt_sat, wl_sat, wc_sat, wk_sat, vital_sat, adj_sat = _effective_weights(
        "07", 0.50, 0.20, 0.15, 0.15, 1.35
    )
    assert adj_sat is True
    assert vital_sat is False
    assert 0.55 < wt_sat < 0.65
    assert round(wt_sat + wl_sat + wc_sat + wk_sat, 4) == 1.0

    # L-V hora pico 7am (1.65x): boost completo (0.50 -> 0.70) y suma 1.0
    wt_pk, wl_pk, wc_pk, wk_pk, _, adj_pk = _effective_weights("07", 0.50, 0.20, 0.15, 0.15, 1.65)
    assert adj_pk is True
    assert wt_pk == 0.70
    assert wt_pk > wt_sat
    assert round(wt_pk + wl_pk + wc_pk + wk_pk, 4) == 1.0

    # Urgencia vital (01) en pico (1.65x): 0.80 -> 0.88 y suma 1.0
    wt_v, wl_v, wc_v, wk_v, vital_v, adj_v = _effective_weights("01", 0.50, 0.20, 0.15, 0.15, 1.65)
    assert adj_v is True
    assert vital_v is True
    assert wt_v == 0.88
    assert round(wt_v + wl_v + wc_v + wk_v, 4) == 1.0
