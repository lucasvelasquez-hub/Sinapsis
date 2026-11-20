export type UrgencyLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type ServiceType =
  | "MEDICAL_CRITICAL"
  | "TRAUMA_RESCUE"
  | "MEDICAL_URGENT"
  | "TRANSFER_ASSISTED"
  | "CRISIS_INTERVENTION";

export interface RequestSummary {
  service_id: string;
  request_datetime: string;
  urgency_level: UrgencyLevel;
  service_type: ServiceType;
  zone_id: string;
  status: string;
  is_synthetic: boolean;
  assigned_unit_id: string | null;
  response_time_min: number | null;
}

export interface RequestContext {
  hour_of_day: number;
  day_of_week: number;
  is_weekend: boolean;
  is_peak_hour: boolean;
  target_response_min: number;
  max_acceptable_min: number;
  sla_label: string;
  zone_demand_4h: number;
  zone_demand_8h: number;
  zone_demand_12h: number;
  demand_pressure_level: string;
}

export interface RequestDetail extends RequestSummary {
  service_duration_min: number | null;
  completion_datetime: string | null;
  context: RequestContext;
}

export interface UnitStatus {
  unit_id: string;
  unit_code: string;
  unit_type: string;
  base_zone_id: string;
  shift: string;
  capacity: number;
  active: boolean;
  simulated_available: boolean;
  busy_until: string | null;
  workload_4h: number;
  workload_8h: number;
  workload_12h: number;
}

export type ExclusionCode =
  | "INACTIVE"
  | "INCOMPATIBLE_TYPE"
  | "INSUFFICIENT_CAPACITY"
  | "OUT_OF_SHIFT"
  | "BUSY_IN_SIMULATION";

export interface ExclusionReason {
  unit_id: string;
  unit_code: string;
  unit_type: string;
  /** Códigos estructurados, alineados con `reasons`. */
  reason_codes: ExclusionCode[];
  reasons: string[];
}

export interface EligibilityEvaluation {
  service_id: string;
  evaluation_datetime: string;
  eligible_units: UnitStatus[];
  excluded_units: ExclusionReason[];
}

export interface RecommendationCandidate {
  unit_id: string;
  unit_code: string;
  unit_type: string;
  base_zone_id: string;
  shift: string;
  rank: number;
  score: number;
  time_penalty: number;
  workload_penalty: number;
  expected_response_min: number;
  estimation_type: string;
  workload_4h: number;
  workload_8h: number;
  workload_12h: number;
  compatibility_rank: number;
  simulated_available: boolean;
  factors: string[];
  warnings: string[];
}

export interface RecommendationOut {
  recommendation_id: string;
  service_id: string;
  simulation_datetime: string;
  status: string;
  eligible_count: number;
  excluded_count: number;
  weights: Record<string, number>;
  candidates: RecommendationCandidate[];
  excluded_units: ExclusionReason[];
}

export interface DecisionOut {
  decision_id: string;
  service_id: string;
  recommendation_id: string | null;
  recommended_unit_id: string | null;
  assigned_unit_id: string | null;
  recommendation_score: number | null;
  accepted: boolean;
  rejection_reason: string | null;
  /** Identificador del despachador que registró la decisión ("SIN_REGISTRO" en las antiguas). */
  dispatcher_id: string;
  /** Motivos de exclusión de la unidad asignada si el despachador anuló la elegibilidad. */
  eligibility_override: string[];
  decision_datetime: string;
}

export interface ScoringConfig {
  config_id: string;
  weight_time: number;
  weight_workload: number;
  weight_cost: number;
  weight_coverage: number;
  cost_enabled: boolean;
  coverage_enabled: boolean;
  updated_at: string;
}

export interface ModelMetric {
  model_name: string;
  split_name: string;
  mae: number;
  median_ae: number;
  p90_ae: number;
  rmse: number;
  is_selected: boolean;
}

export interface AnalyticsOverview {
  total_services: number;
  pending_requests: number;
  avg_response_min: number;
  sla_compliance_rate: number;
  total_units: number;
  available_units_sim: number;
  total_decisions: number;
  accepted_decisions: number;
  simulation_datetime: string;
  selected_model: string;
  model_metrics: ModelMetric[];
}

export interface DemandBucket {
  dimension: string;
  dimension_value: string;
  service_count: number;
  avg_response_min: number;
  sla_compliance_rate: number;
}

export interface AnalyticsDemand {
  by_zone: DemandBucket[];
  by_hour: DemandBucket[];
  by_day: DemandBucket[];
  by_urgency: DemandBucket[];
  by_service_type: DemandBucket[];
  by_unit: DemandBucket[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  timestamp: string;
}
