/** Vocabularios del dataset: vienen de GET /catalog, no de listas fijas en el front. */
export type UrgencyLevel = string;
export type ServiceType = string;

export interface CatalogUrgency {
  code: UrgencyLevel;
  description?: string;
  manchester_scale?: string;
  target_response_min: number;
}

export interface Catalog {
  /** De mayor a menor urgencia (menor objetivo primero). */
  urgencies: CatalogUrgency[];
  service_types: ServiceType[];
  service_types_by_urgency?: Record<string, ServiceType[]>;
  zones: string[];
  unit_types: string[];
  shifts: string[];
}

export interface RequestSummary {
  service_id: string;
  request_datetime: string;
  urgency_level: UrgencyLevel;
  service_type: ServiceType;
  zone_id: string;
  status: string;
  is_synthetic: boolean;
  assigned_unit_id: string | null;
  arrival_datetime?: string | null;
  response_time_min: number | null;
}

export interface RequestContext {
  hour_of_day: number;
  day_of_week: number;
  is_weekend: boolean;
  is_peak_hour: boolean;
  target_response_min: number;
  zone_demand_4h: number;
  zone_demand_8h: number;
  zone_demand_12h: number;
  demand_pressure_level: string;
}

export interface RequestDetail extends RequestSummary {
  assignment_datetime: string | null;
  arrival_datetime: string | null;
  closure_datetime: string | null;
  service_duration_min: number | null;
  context: RequestContext;
}

export interface ReclassifyOut extends RequestDetail {
  release_recommended: boolean;
  motivo: string | null;
}

export interface UnitStatus {
  unit_id: string;
  unit_type: string;
  base_id: string;
  shift: string;
  capacity: number;
  cost_per_km?: number | null;
  cost_per_hour?: number | null;
  current_zone_id?: string | null;
  current_lat?: number | null;
  current_lon?: number | null;
  distance_km?: number | null;
  observation?: string | null;
  active: boolean;
  simulated_available: boolean;
  busy_until: string | null;
  workload_4h: number;
  workload_8h: number;
  workload_12h: number;
  diversion_of_service_id?: string | null;
  rule_factors?: string[];
}

export type ExclusionCode =
  | "INACTIVE"
  | "INCOMPATIBLE_TYPE"
  | "INSUFFICIENT_CAPACITY"
  | "OUT_OF_SHIFT"
  | "BUSY_IN_SIMULATION"
  | "OUT_OF_RANGE";

export interface ExclusionReason {
  unit_id: string;
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
  unit_type: string;
  base_id: string;
  shift: string;
  rank: number;
  score: number;
  time_penalty: number;
  workload_penalty: number;
  cost_penalty?: number;
  coverage_penalty?: number;
  expected_response_min: number;
  distance_km?: number | null;
  /** Predicción del modelo ML (PREDICHO); no ordena el Top 3, se muestra para evaluarla. */
  ml_expected_min?: number | null;
  estimated_travel_min?: number | null;
  estimated_cost?: number | null;
  recommended_role?: string | null;
  paired_unit_id?: string | null;
  estimation_type: string;
  workload_4h: number;
  workload_8h: number;
  workload_12h: number;
  compatibility_rank: number;
  simulated_available: boolean;
  factors: string[];
  warnings: string[];
  diversion_of_service_id?: string | null;
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

export interface KpiDefinition {
  id_kpi: string;
  nombre: string;
  definicion: string;
  unidad: string;
  meta_referencia: string;
  linea_base_ficticia: string;
  valor_actual_db: string | null;
  valor_simulado?: string | null;
  procedencia_simulado?: "SIMULADO" | "OBSERVADO" | null;
}

export interface BaselineByClassification {
  clasificacion: string;
  descripcion: string;
  escala_manchester: string;
  servicios: number;
  tiempo_objetivo_min: number;
  tr_mediana_min: number;
  tr_promedio_min: number;
  tr_p90_min: number;
  pct_cumple_objetivo: number;
  pct_traslado: number;
}

export interface KpisOverview {
  kpis: KpiDefinition[];
  linea_base: BaselineByClassification[];
}

export interface ScenarioSummary {
  id_escenario: string;
  nombre: string;
  descripcion: string;
  fecha_hora_inicio: string;
  tipo_dia: string;
  duracion_min: number;
  factor_trafico_inicio: number;
  objetivo_aprendizaje: string;
  n_solicitudes: number;
}

export interface ScenarioRequestEval {
  id_solicitud: string;
  minuto_llegada: number;
  id_zona: string;
  clasificacion_inicial: string;
  motivo_consulta: string;
  discriminador: string;
  recommended_unit_id: string | null;
  recommended_unit_type: string | null;
  recommended_score: number | null;
  distance_km?: number | null;
  estimated_travel_min: number | null;
  estimated_cost: number | null;
  recommended_role: string | null;
  paired_unit_id: string | null;
  factors: string[];
  warnings: string[];
  reference_unit_id: string | null;
  reference_unit_type: string | null;
  reference_role: string | null;
  reference_eta_min: number | null;
  reference_distance_km?: number | null;
  reference_estimated_cost?: number | null;
  reference_justification: string | null;
  reference_paired_unit_id?: string | null;
  reference_paired_unit_type?: string | null;
  reference_paired_role?: string | null;
  matches_reference_unit: boolean;
  matches_reference_type: boolean;
  matches_paired_unit?: boolean;
  matches_paired_type?: boolean;
  sla_target_min?: number | null;
  sla_met_core?: boolean | null;
  sla_met_ref?: boolean | null;
  eta_delta_min?: number | null;
}

export interface ScenarioEvaluation {
  scenario: ScenarioSummary;
  results: ScenarioRequestEval[];
  unit_match_rate: number;
  type_match_rate: number;
  paired_match_rate?: number | null;
  avg_eta_core_min?: number | null;
  avg_eta_ref_min?: number | null;
  eta_delta_min?: number | null;
  sla_core_pct?: number | null;
  sla_ref_pct?: number | null;
  events_applied?: number;
}

export interface ScenarioBatchItem {
  id_escenario: string;
  nombre: string;
  objetivo_aprendizaje: string;
  n_solicitudes: number;
  events_applied: number;
  unit_matches: number;
  type_matches: number;
  unit_match_rate: number;
  type_match_rate: number;
  paired_match_rate: number | null;
  avg_eta_core_min: number | null;
  avg_eta_ref_min: number | null;
  eta_delta_min: number | null;
  sla_core_pct: number;
  sla_ref_pct: number;
  avg_cost_core: number | null;
  avg_cost_ref: number | null;
  avg_dist_core_km: number | null;
  avg_dist_ref_km: number | null;
}

export interface AllScenariosTotals {
  total_scenarios: number;
  total_requests: number;
  unit_matches: number;
  type_matches: number;
  unit_match_rate: number;
  type_match_rate: number;
  avg_eta_core_min: number | null;
  avg_eta_ref_min: number | null;
  eta_delta_min: number | null;
  sla_core_pct: number;
  sla_ref_pct: number;
  sla_vital_core_pct: number;
  sla_vital_ref_pct: number;
  avg_cost_core: number | null;
  avg_cost_ref: number | null;
  avg_dist_core_km: number | null;
  avg_dist_ref_km: number | null;
  discrepancy_counts: Record<string, number>;
  r01_incompatible_count: number;
  r03_vital_without_ambulance_or_pair: number;
  r04_stabilization_count: number;
  r06_diversion_detected_count: number;
  d03_green_uncovered_warnings: number;
  d05_tam_on_02_warnings: number;
  d06_transfer_tab_activations: number;
}

export interface AllScenariosEvaluation {
  provenance: "SIMULADO";
  scenarios: ScenarioBatchItem[];
  totals: AllScenariosTotals;
}

export interface SimZone {
  zone_id: string;
  municipality: string;
  comuna: string;
  lat_centroid: number;
  lon_centroid: number;
  relative_demand: string;
}

export interface SimBase {
  base_id: string;
  name: string;
  municipality: string;
  zone_id: string;
  lat: number;
  lon: number;
}

export interface SimCareCenter {
  center_id: string;
  name: string;
  zone_id: string;
  complexity_level: string;
  lat: number;
  lon: number;
}

export type UnitOperationalState =
  | "DISPONIBLE"
  | "RETORNANDO"
  | "EN_RUTA"
  | "EN_ATENCION"
  | "EN_TRASLADO"
  | "FUERA_SERVICIO";

export interface SimUnit {
  unit_id: string;
  unit_type: string;
  base_id: string;
  active: boolean;
  simulated_available: boolean;
  operational_state?: UnitOperationalState;
  busy_until: string | null;
  current_zone_id: string | null;
  lat: number;
  lon: number;
}

export interface SimRequest {
  service_id: string;
  request_datetime: string;
  arrival_datetime?: string | null;
  urgency_level: string;
  service_type: string;
  zone_id: string;
  status: string;
  closure_state?: string | null;
  assigned_unit_id: string | null;
  lat: number;
  lon: number;
}

export interface SimulationState {
  current_sim_datetime: string;
  day_type?: string;
  traffic_factor?: number;
  zones: SimZone[];
  bases: SimBase[];
  care_centers?: SimCareCenter[];
  units: SimUnit[];
  active_requests: SimRequest[];
}

export interface CompleteServiceOut {
  service_id: string;
  status: string;
  closure_state: string;
  destination_center?: string | null;
  released_unit_id: string | null;
  stretcher_retention_min?: number | null;
  closure_datetime: string;
}

export interface ReclassifyServiceOut {
  service_id: string;
  previous_urgency_level: string;
  urgency_level: string;
  manchester_scale: string;
  origin: string;
}

export interface DivertUnitOut {
  unit_id: string;
  target_service_id: string;
  returned_service_id: string;
  decision_id: string;
}

export interface AdvanceClockOut {
  current_sim_datetime: string;
  day_type: string;
  traffic_factor: number;
  /** Solicitudes del flujo mensual que entraron con este avance. */
  injected_requests: number;
}

export interface FlowInfo {
  name: string;
  month: string;
  total: number;
}

export interface FlowStatus {
  active: boolean;
  name: string | null;
  month: string | null;
  total: number;
  injected: number;
  remaining: number;
  next_request_datetime: string | null;
  last_request_datetime: string | null;
  finished: boolean;
}

export interface SimulationEvaluationRow {
  service_id: string;
  request_datetime: string;
  urgency_level: string;
  zone_id: string;
  recommended_unit_id: string | null;
  assigned_unit_id: string | null;
  /** null: el móvil asignado no estaba en el Top 3. */
  assigned_rank: number | null;
  followed_top1: boolean;
  /** Tiempo esperado de la recomendación (el que ordena el Top 3). */
  predicted_min: number | null;
  /** Origen de predicted_min, p. ej. MATRIX_TRAFFIC_ESTIMATE. */
  estimation_type: string | null;
  /** PREDICHO por el modelo ML para el móvil asignado. */
  ml_predicted_min: number | null;
  /** SIMULADO: llegada − solicitud con el reloj de simulación. */
  simulated_min: number | null;
  error_min: number | null;
  ml_error_min: number | null;
}

export interface SimulationEvaluation {
  scope: "flow" | "all";
  summary: {
    requests: number;
    decided: number;
    arrived: number;
    followed_top1_rate: number | null;
    mae_min: number | null;
    /** > 0: la estimación subestima el tiempo. */
    bias_min: number | null;
    within_5_min_rate: number | null;
    ml_mae_min: number | null;
    ml_bias_min: number | null;
    ml_within_5_min_rate: number | null;
  };
  rows: SimulationEvaluationRow[];
}
