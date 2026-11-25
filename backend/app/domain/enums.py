"""Closed vocabularies of the domain. StrEnum keeps JSON/DB values as plain strings."""

from enum import StrEnum


class ServiceStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class RecommendationStatus(StrEnum):
    GENERATED = "GENERATED"
    NO_ELIGIBLE_UNITS = "NO_ELIGIBLE_UNITS"


class ExclusionCode(StrEnum):
    """Why a unit fails A(i,j) = E·S·D."""

    INACTIVE = "INACTIVE"
    INCOMPATIBLE_TYPE = "INCOMPATIBLE_TYPE"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
    OUT_OF_SHIFT = "OUT_OF_SHIFT"
    BUSY_IN_SIMULATION = "BUSY_IN_SIMULATION"
    OUT_OF_RANGE = "OUT_OF_RANGE"


class UrgencyLevel(StrEnum):
    """Clasificación EMI de mayor a menor prioridad (CHECK `ck_services_urgency`).

    Orden: 01 (ROJO, 15m) > 02 (NARANJA, 20m) > 07 (AMARILLO, 45m) > 03 (VERDE, 90m)
    > 06 (AZUL, 180m).
    """

    EMI_01 = "01"
    EMI_02 = "02"
    EMI_07 = "07"
    EMI_03 = "03"
    EMI_06 = "06"


class CompatibilityLevel(StrEnum):
    """Matriz de compatibilidad clasificación EMI vs tipo de móvil (doc 03)."""

    PREFERIDA = "PREFERIDA"
    PERMITIDA = "PERMITIDA"
    SOLO_ESTABILIZACION = "SOLO_ESTABILIZACION"
    NO_RECOMENDADA = "NO_RECOMENDADA"
    NO_PERMITIDA = "NO_PERMITIDA"


class UnitRole(StrEnum):
    """Rol operativo de la móvil en el servicio."""

    ATENCION = "ATENCION"
    ATENCION_Y_TRASLADO = "ATENCION_Y_TRASLADO"
    PRIMER_RESPONDIENTE_ESTABILIZACION = "PRIMER_RESPONDIENTE_ESTABILIZACION"
    TRASLADO = "TRASLADO"
