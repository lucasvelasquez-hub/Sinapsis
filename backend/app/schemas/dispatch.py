from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import ExclusionCode, RecommendationStatus, ServiceStatus, UrgencyLevel


class ORMModel(BaseModel):
    """Output schema readable straight from an ORM object (`Model.model_validate(orm)`)."""

    model_config = ConfigDict(from_attributes=True)


class RequestSummary(ORMModel):
    service_id: str
    request_datetime: datetime
    urgency_level: str
    manchester_scale: str | None = None
    service_type: str  # motivo_consulta del dataset: GET /api/v1/catalog
    discriminator: str | None = None
    channel: str | None = None
    zone_id: str
    status: ServiceStatus
    closure_state: str | None = None
    is_synthetic: bool
    assigned_unit_id: str | None = None
    response_time_min: float | None = None


class RequestContext(BaseModel):
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    is_peak_hour: bool
    target_response_min: int
    zone_demand_4h: int
    zone_demand_8h: int
    zone_demand_12h: int
    demand_pressure_level: str


class RequestDetail(RequestSummary):
    assignment_datetime: datetime | None = None
    arrival_datetime: datetime | None = None
    closure_datetime: datetime | None = None
    service_duration_min: float | None = None
    context: RequestContext


class ReclassifyIn(BaseModel):
    urgency_level: UrgencyLevel
    origen: Literal["RECLASIFICACION_TELEFONICA", "RECLASIFICACION_EN_SITIO"]
    motivo_consulta: str = Field(..., min_length=1, max_length=128)
    discriminador: str = Field(..., min_length=1, max_length=128)
    dispatcher_id: str = Field(
        ...,
        min_length=2,
        max_length=64,
        pattern=r"^[\w.@-]+$",
        description="Identificador del despachador que reclasifica (sin autenticación aún).",
    )

    @field_validator("dispatcher_id", mode="before")
    @classmethod
    def _strip_dispatcher(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReclassifyOut(RequestDetail):
    release_recommended: bool = False
    motivo: str | None = None


class SimulateRequestCreate(BaseModel):
    urgency_level: UrgencyLevel
    service_type: str = Field(..., min_length=1, max_length=128)
    zone_id: str = Field(..., min_length=1, max_length=32)
    discriminator: str | None = Field(default=None, max_length=128)
    channel: str | None = Field(default="TELEFONO", max_length=24)
    request_datetime: datetime | None = None

    @field_validator("request_datetime")
    @classmethod
    def _naive_operational_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            raise ValueError("request_datetime debe ser hora local operativa, sin zona horaria")
        return value


class UnitStatusOut(BaseModel):
    unit_id: str
    unit_type: str
    base_id: str
    shift: str
    capacity: int
    cost_per_km: float | None = None
    cost_per_hour: float | None = None
    current_zone_id: str | None = None
    current_lat: float | None = None
    current_lon: float | None = None
    observation: str | None = None
    active: bool
    simulated_available: bool
    busy_until: datetime | None = None
    workload_4h: int
    workload_8h: int
    workload_12h: int
    diversion_of_service_id: str | None = None
    rule_factors: list[str] = []


class ExclusionReason(BaseModel):
    unit_id: str
    unit_type: str
    reason_codes: list[ExclusionCode]
    reasons: list[str]

    @model_validator(mode="before")
    @classmethod
    def _derive_codes_from_legacy_reasons(cls, data: Any) -> Any:
        if isinstance(data, dict) and "reason_codes" not in data:
            reasons = data.get("reasons") or []
            data = {**data, "reason_codes": [r.split(":", 1)[0] for r in reasons]}
        return data


class EligibilityEvaluation(BaseModel):
    service_id: str
    evaluation_datetime: datetime
    eligible_units: list[UnitStatusOut]
    excluded_units: list[ExclusionReason]


class RecommendationCandidateOut(BaseModel):
    unit_id: str
    unit_type: str
    base_id: str
    shift: str
    rank: int
    score: float
    time_penalty: float
    workload_penalty: float
    cost_penalty: float = 0.0
    coverage_penalty: float = 0.0
    expected_response_min: float
    distance_km: float | None = None
    estimated_travel_min: float | None = None
    estimated_cost: float | None = None
    recommended_role: str | None = None
    paired_unit_id: str | None = None
    estimation_type: str
    workload_4h: int
    workload_8h: int
    workload_12h: int
    compatibility_rank: int
    simulated_available: bool
    factors: list[str]
    warnings: list[str]
    diversion_of_service_id: str | None = None


class RecommendationOut(BaseModel):
    recommendation_id: str
    service_id: str
    simulation_datetime: datetime
    status: RecommendationStatus
    eligible_count: int
    excluded_count: int
    weights: dict[str, float]
    candidates: list[RecommendationCandidateOut]
    excluded_units: list[ExclusionReason]


class EvaluateRecommendationRequest(BaseModel):
    service_id: str


class DecisionCreate(BaseModel):
    service_id: str
    recommendation_id: str | None = None
    recommended_unit_id: str | None = None
    assigned_unit_id: str | None = None
    recommendation_score: float | None = Field(
        default=None,
        deprecated=True,
        description="Ignorado: el score se toma de la recomendación persistida.",
    )
    accepted: bool
    rejection_reason: str | None = None
    dispatcher_id: str = Field(
        ...,
        min_length=2,
        max_length=64,
        pattern=r"^[\w.@-]+$",
        description="Identificador del despachador que decide (sin autenticación aún).",
    )

    @field_validator("dispatcher_id", mode="before")
    @classmethod
    def _strip_dispatcher(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DecisionOut(ORMModel):
    decision_id: str
    service_id: str
    recommendation_id: str | None
    recommended_unit_id: str | None
    assigned_unit_id: str | None
    recommendation_score: float | None
    accepted: bool
    rejection_reason: str | None
    dispatcher_id: str
    eligibility_override: list[str] = Field(default_factory=list)
    decision_datetime: datetime


class ScoringConfigOut(ORMModel):
    config_id: str
    weight_time: float
    weight_workload: float
    weight_cost: float
    weight_coverage: float
    cost_enabled: bool
    coverage_enabled: bool
    updated_at: datetime


class ScoringConfigUpdate(BaseModel):
    weight_time: float = Field(..., ge=0.0, le=1.0)
    weight_workload: float = Field(..., ge=0.0, le=1.0)
    weight_cost: float = Field(default=0.0, ge=0.0, le=1.0)
    weight_coverage: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "ScoringConfigUpdate":
        total = self.weight_time + self.weight_workload + self.weight_cost + self.weight_coverage
        if abs(total - 1.0) > 1e-3:
            raise ValueError("La suma de pesos (tiempo + carga + costo + cobertura) debe ser 1.0")
        return self
