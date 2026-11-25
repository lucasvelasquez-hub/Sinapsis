from datetime import datetime

from pydantic import BaseModel, Field


class SimZoneOut(BaseModel):
    zone_id: str
    municipality: str
    comuna: str
    lat_centroid: float
    lon_centroid: float
    relative_demand: str


class SimBaseOut(BaseModel):
    base_id: str
    name: str
    municipality: str
    zone_id: str
    lat: float
    lon: float


class SimCareCenterOut(BaseModel):
    center_id: str
    name: str
    zone_id: str
    complexity_level: str
    lat: float
    lon: float


class SimUnitOut(BaseModel):
    unit_id: str
    unit_type: str
    base_id: str
    active: bool
    simulated_available: bool
    operational_state: str = "DISPONIBLE"
    busy_until: datetime | None = None
    current_zone_id: str | None = None
    lat: float
    lon: float


class SimRequestOut(BaseModel):
    service_id: str
    request_datetime: datetime
    arrival_datetime: datetime | None = None
    urgency_level: str
    service_type: str
    zone_id: str
    status: str
    closure_state: str | None = None
    assigned_unit_id: str | None = None
    lat: float
    lon: float


class SimulationStateOut(BaseModel):
    current_sim_datetime: datetime
    day_type: str = "LUNES_A_VIERNES"
    traffic_factor: float = 1.0
    zones: list[SimZoneOut]
    bases: list[SimBaseOut]
    care_centers: list[SimCareCenterOut] = []
    units: list[SimUnitOut]
    active_requests: list[SimRequestOut]


class UnitPositionIn(BaseModel):
    unit_id: str
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    zone_id: str | None = None


class PositionsBatchIn(BaseModel):
    positions: list[UnitPositionIn] = Field(..., min_length=1, max_length=100)


class PositionsBatchOut(BaseModel):
    updated: int


class CompleteServiceIn(BaseModel):
    closure_state: str = Field(
        default="ATENDIDO_EN_SITIO",
        pattern=r"^(ATENDIDO_EN_SITIO|TRASLADADO|RESUELTO_TELEFONICAMENTE|CANCELADO_POR_USUARIO|NO_UBICADO)$",
    )
    destination_center_id: str | None = None


class CompleteServiceOut(BaseModel):
    service_id: str
    status: str
    closure_state: str
    destination_center: str | None = None
    released_unit_id: str | None = None
    stretcher_retention_min: int | None = None
    closure_datetime: datetime


class ReclassifyServiceIn(BaseModel):
    new_urgency_level: str = Field(..., pattern=r"^(01|02|07|03|06)$")
    origin: str = Field(
        default="RECLASIFICACION_TELEFONICA",
        pattern=r"^(RECLASIFICACION_TELEFONICA|RECLASIFICACION_EN_SITIO)$",
    )


class ReclassifyServiceOut(BaseModel):
    service_id: str
    previous_urgency_level: str
    urgency_level: str
    manchester_scale: str
    origin: str


class DivertUnitIn(BaseModel):
    unit_id: str = Field(..., min_length=1, max_length=64)
    target_service_id: str = Field(..., min_length=1, max_length=64)
    dispatcher_id: str = Field(..., min_length=1, max_length=64)


class DivertUnitOut(BaseModel):
    unit_id: str
    target_service_id: str
    returned_service_id: str
    decision_id: str


class ArriveServiceOut(BaseModel):
    service_id: str
    arrival_datetime: datetime


class AdvanceClockIn(BaseModel):
    minutes: int = Field(default=10, ge=1, le=720)


class AdvanceClockOut(BaseModel):
    current_sim_datetime: datetime
    day_type: str
    traffic_factor: float


class GenerateRequestsIn(BaseModel):
    count: int = Field(default=4, ge=1, le=20)


class GenerateRequestsOut(BaseModel):
    created: list[SimRequestOut]
