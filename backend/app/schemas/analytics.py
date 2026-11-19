from pydantic import BaseModel


class ModelMetricOut(BaseModel):
    model_name: str
    split_name: str
    mae: float
    median_ae: float
    p90_ae: float
    rmse: float
    is_selected: bool


class AnalyticsOverviewOut(BaseModel):
    total_services: int
    pending_requests: int
    avg_response_min: float
    sla_compliance_rate: float
    total_units: int
    available_units_sim: int
    total_decisions: int
    accepted_decisions: int
    simulation_datetime: str
    selected_model: str
    model_metrics: list[ModelMetricOut]


class DemandBucketOut(BaseModel):
    dimension: str
    dimension_value: str
    service_count: int
    avg_response_min: float
    sla_compliance_rate: float


class AnalyticsDemandOut(BaseModel):
    by_zone: list[DemandBucketOut]
    by_hour: list[DemandBucketOut]
    by_day: list[DemandBucketOut]
    by_urgency: list[DemandBucketOut]
    by_service_type: list[DemandBucketOut]
    by_unit: list[DemandBucketOut]
