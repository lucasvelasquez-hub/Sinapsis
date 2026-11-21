from pydantic import BaseModel


class UrgencyOut(BaseModel):
    code: str
    description: str = ""
    manchester_scale: str = ""
    target_response_min: int


class CatalogOut(BaseModel):
    """Vocabularios del dataset cargado: el front no mantiene listas propias."""

    urgencies: list[UrgencyOut]  # de mayor a menor urgencia (menor objetivo primero)
    service_types: list[str]
    service_types_by_urgency: dict[str, list[str]] = {}
    zones: list[str]
    unit_types: list[str]
    shifts: list[str]
