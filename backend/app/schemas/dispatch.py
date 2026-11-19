from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UrgencyLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ServiceType = Literal[
    "MEDICAL_CRITICAL",
    "TRAUMA_RESCUE",
    "MEDICAL_URGENT",
    "TRANSFER_ASSISTED",
    "CRISIS_INTERVENTION",
]


class RequestSummary(BaseModel):
    service_id: str
    request_datetime: datetime
    urgency_level: str
    service_type: str
    zone_id: str
    status: str
    is_synthetic: bool
    assigned_unit_id: str | None = None
    response_time_min: float | None = None


class RequestContext(BaseModel):
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    is_peak_hour: bool
    target_response_min: int
    max_acceptable_min: int
    sla_label: str
    zone_demand_4h: int
    zone_demand_8h: int
    zone_demand_12h: int
    demand_pressure_level: str


class RequestDetail(RequestSummary):
    service_duration_min: float | None = None
    completion_datetime: datetime | None = None
    context: RequestContext


class SimulateRequestCreate(BaseModel):
    urgency_level: UrgencyLevel
    service_type: ServiceType
    zone_id: str = Field(..., pattern=r"^ZONE-0[1-8]$")
    request_datetime: datetime | None = None


class UnitStatusOut(BaseModel):
    unit_id: str
    unit_code: str
    unit_type: str
    base_zone_id: str
    shift: str
    capacity: int
    active: bool
    simulated_available: bool
    busy_until: datetime | None = None
    workload_4h: int
    workload_8h: int
    workload_12h: int


class ExclusionReason(BaseModel):
    unit_id: str
    unit_code: str
    unit_type: str
    reasons: list[str]


class EligibilityEvaluation(BaseModel):
    service_id: str
    evaluation_datetime: datetime
    eligible_units: list[UnitStatusOut]
    excluded_units: list[ExclusionReason]


class RecommendationCandidateOut(BaseModel):
    unit_id: str
    unit_code: str
    unit_type: str
    base_zone_id: str
    shift: str
    rank: int
    score: float
    time_penalty: float
    workload_penalty: float
    expected_response_min: float
    estimation_type: str
    workload_4h: int
    workload_8h: int
    workload_12h: int
    compatibility_rank: int
    simulated_available: bool
    factors: list[str]
    warnings: list[str]


class RecommendationOut(BaseModel):
    recommendation_id: str
    service_id: str
    simulation_datetime: datetime
    status: str
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
    recommendation_score: float | None = None
    accepted: bool
    rejection_reason: str | None = None


class DecisionOut(BaseModel):
    decision_id: str
    service_id: str
    recommendation_id: str | None
    recommended_unit_id: str | None
    assigned_unit_id: str | None
    recommendation_score: float | None
    accepted: bool
    rejection_reason: str | None
    decision_datetime: datetime


class ScoringConfigOut(BaseModel):
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
