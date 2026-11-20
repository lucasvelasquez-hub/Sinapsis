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


class UrgencyLevel(StrEnum):
    """Urgencias del dataset, de mayor a menor (CHECK `ck_services_urgency`)."""

    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"
