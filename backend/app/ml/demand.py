"""Demanda previa a cada solicitud, compartida por entrenamiento y serving (sin fuga temporal).

Cuenta solicitudes *estrictamente anteriores* a la de referencia: la ventana de N horas
incluye el instante exacto `ref - N h` y excluye `ref`. Es la regla de
`domain.temporal.window_counts`.

Función pura: el entrenamiento le pasa el historial completo; el serving, solo las últimas
`HISTORY_HOURS` horas (suficiente para todas las ventanas), y el resultado es idéntico.
"""

from bisect import bisect_left
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

ZONE_WINDOWS_HOURS = (4, 8, 12)
SYSTEM_WINDOW_HOURS = 1
HISTORY_HOURS = max(ZONE_WINDOWS_HOURS)

DEMAND_COLUMNS = [
    "zone_demand_4h",
    "zone_demand_8h",
    "zone_demand_12h",
    "system_demand_1h",
]


def _count_before(sorted_ts: Sequence[datetime], ref: datetime, hours: int) -> int:
    """Eventos en [ref - hours, ref). `sorted_ts` debe estar ordenada."""
    return bisect_left(sorted_ts, ref) - bisect_left(sorted_ts, ref - timedelta(hours=hours))


def demand_features(
    ref: datetime, zone_ts: Sequence[datetime], system_ts: Sequence[datetime]
) -> dict[str, Any]:
    """Demanda de la zona (4/8/12 h) y del sistema (1 h) antes de `ref`.

    `zone_ts`: instantes de solicitudes de la zona; `system_ts`: de todas las zonas.
    Ambas ordenadas ascendentemente.
    """
    return {
        "zone_demand_4h": _count_before(zone_ts, ref, 4),
        "zone_demand_8h": _count_before(zone_ts, ref, 8),
        "zone_demand_12h": _count_before(zone_ts, ref, 12),
        "system_demand_1h": _count_before(system_ts, ref, SYSTEM_WINDOW_HOURS),
    }
