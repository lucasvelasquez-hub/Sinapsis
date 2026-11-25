"""Orden de asignación del documento 03. Sin SQL y sin HTTP.

El primer criterio que distingue, gana. La zona no entra en esta comparación.
"""

from dataclasses import dataclass

ARRIVAL_BAND_MIN = 3.0
VMD_ADVANTAGE_MIN = 12.0
COVERAGE_MAX_MIN = 20.0
D07_NEAR_MIN = 15.0
R02_ASSIGN_MAX_MIN = 2.0

URGENCY_RANK: dict[str, int] = {"01": 0, "02": 1, "07": 2, "03": 3, "06": 4}

VITAL = frozenset({"01", "02"})
GREEN = frozenset({"07", "03", "06"})
AMBULANCE_TYPES = frozenset({"TAM", "TAB"})

WARN_D03 = "Regla D03: deja zona de demanda ALTA sin ambulancia <=20 min"
WARN_D05 = "Regla D05: hay TAB disponible; reservar TAM para emergencias 01"
WARN_D06 = "Regla D06: 07 con posible traslado; TAB dentro de la meta"

TRANSFER_MOTIVOS = frozenset({"Caídas", "Heridas"})
TRANSFER_DISCRIMINADOR = "Signos de deshidratación"


@dataclass(frozen=True)
class PolicyUnit:
    unit_id: str
    unit_type: str
    arrival_min: float
    cost: float
    workload: float
    leaves_alta_uncovered: bool
    diverted_from_service_id: str | None


@dataclass(frozen=True)
class RankedUnit:
    unit: PolicyUnit
    tier: int
    role: str
    paired_unit_id: str | None
    factors: list[str]
    warnings: list[str]


def is_transfer_likely(motivo: str | None, discriminador: str | None) -> bool:
    if motivo in TRANSFER_MOTIVOS:
        return True
    return discriminador == TRANSFER_DISCRIMINADOR


def rank_units(
    urgency: str,
    target_min: float,
    units: list[PolicyUnit],
    *,
    transfer_likely: bool,
) -> list[RankedUnit]:
    """Ordena móviles. tier 0 puede ganar; tier 1 quedó hundida por D03."""
    if not units:
        return []

    if urgency in VITAL:
        ordered = _rank_vital(units, urgency)
        demoted: set[str] = set()
    else:
        ordered, demoted = _rank_green(units, urgency, target_min, transfer_likely)

    has_tab = any(u.unit_type == "TAB" for u in units)
    d06_active = _d06_active(urgency, target_min, units, transfer_likely)
    ranked: list[RankedUnit] = []
    for unit in ordered:
        warnings: list[str] = []
        if unit.leaves_alta_uncovered:
            warnings.append(WARN_D03)
        if urgency == "02" and unit.unit_type == "TAM" and has_tab:
            warnings.append(WARN_D05)
        if d06_active and unit.unit_type == "TAB" and unit.arrival_min <= target_min:
            warnings.append(WARN_D06)
        ranked.append(
            RankedUnit(
                unit=unit,
                tier=1 if unit.unit_id in demoted else 0,
                role="ATENCION",
                paired_unit_id=None,
                factors=[f"Llegada estimada: {unit.arrival_min:.1f} min"],
                warnings=warnings,
            )
        )
    return ranked


def _rank_vital(units: list[PolicyUnit], urgency: str) -> list[PolicyUnit]:
    ambulances = [u for u in units if u.unit_type in AMBULANCE_TYPES]
    others = [u for u in units if u.unit_type not in AMBULANCE_TYPES]
    return _band_sort(ambulances, urgency) + _band_sort(others, urgency)


def _rank_green(
    units: list[PolicyUnit],
    urgency: str,
    target_min: float,
    transfer_likely: bool,
) -> tuple[list[PolicyUnit], set[str]]:
    meets = [u for u in units if u.arrival_min <= target_min]
    misses = [u for u in units if u.arrival_min > target_min]
    ordered_meets = _apply_d06(meets, urgency, target_min, transfer_likely)
    alternative = any(u.arrival_min <= target_min and not u.leaves_alta_uncovered for u in units)
    if not alternative:
        return ordered_meets + _band_sort(misses, urgency), set()
    front = [u for u in ordered_meets if not u.leaves_alta_uncovered]
    back = [u for u in ordered_meets if u.leaves_alta_uncovered]
    return front + back + _band_sort(misses, urgency), {u.unit_id for u in back}


def _apply_d06(
    meets: list[PolicyUnit],
    urgency: str,
    target_min: float,
    transfer_likely: bool,
) -> list[PolicyUnit]:
    if not _d06_active(urgency, target_min, meets, transfer_likely):
        return _band_sort(meets, urgency)
    tabs = [u for u in meets if u.unit_type == "TAB"]
    rest = [u for u in meets if u.unit_type != "TAB"]
    return _band_sort(tabs, urgency) + _band_sort(rest, urgency)


def _d06_active(
    urgency: str,
    target_min: float,
    units: list[PolicyUnit],
    transfer_likely: bool,
) -> bool:
    return (
        urgency == "07"
        and transfer_likely
        and any(u.unit_type == "TAB" and u.arrival_min <= target_min for u in units)
    )


def _band_sort(units: list[PolicyUnit], urgency: str) -> list[PolicyUnit]:
    if not units:
        return []
    best = min(u.arrival_min for u in units)
    inside = [u for u in units if u.arrival_min < best + ARRIVAL_BAND_MIN]
    outside = [u for u in units if u.arrival_min >= best + ARRIVAL_BAND_MIN]
    inside.sort(key=lambda u: _inside_key(u, urgency))
    outside.sort(key=lambda u: (u.arrival_min, u.unit_id))
    return inside + outside


def _inside_key(unit: PolicyUnit, urgency: str) -> tuple[float, int, float, float, str]:
    tam_penalty = 1 if urgency == "02" and unit.unit_type == "TAM" else 0
    return (unit.cost, tam_penalty, unit.workload, unit.arrival_min, unit.unit_id)
