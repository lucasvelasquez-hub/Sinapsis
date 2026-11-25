"""Tests unitarios puros de las reglas de negocio EMI en recommendation_service."""

from app.services.recommendation_service import (
    _d06_possible_transfer,
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
