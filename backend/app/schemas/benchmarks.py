from typing import Literal

from pydantic import BaseModel


class KpiDefinitionOut(BaseModel):
    id_kpi: str
    nombre: str
    definicion: str
    unidad: str
    meta_referencia: str
    linea_base_ficticia: str
    valor_actual_db: str | None = None
    valor_simulado: str | None = None
    procedencia_simulado: Literal["SIMULADO", "OBSERVADO"] | None = None


class BaselineByClassificationOut(BaseModel):
    clasificacion: str
    descripcion: str
    escala_manchester: str
    servicios: int
    tiempo_objetivo_min: int
    tr_mediana_min: float
    tr_promedio_min: float
    tr_p90_min: float
    pct_cumple_objetivo: float
    pct_traslado: float


class KpisOverviewOut(BaseModel):
    kpis: list[KpiDefinitionOut]
    linea_base: list[BaselineByClassificationOut]


class ScenarioSummaryOut(BaseModel):
    id_escenario: str
    nombre: str
    descripcion: str
    fecha_hora_inicio: str
    tipo_dia: str
    duracion_min: int
    factor_trafico_inicio: float
    objetivo_aprendizaje: str
    n_solicitudes: int


class ScenarioRequestEvalOut(BaseModel):
    id_solicitud: str
    minuto_llegada: int
    id_zona: str
    clasificacion_inicial: str
    motivo_consulta: str
    discriminador: str
    recommended_unit_id: str | None
    recommended_unit_type: str | None
    recommended_score: float | None
    distance_km: float | None = None
    estimated_travel_min: float | None
    estimated_cost: float | None
    recommended_role: str | None
    paired_unit_id: str | None
    factors: list[str]
    warnings: list[str]
    reference_unit_id: str | None
    reference_unit_type: str | None
    reference_role: str | None
    reference_eta_min: float | None
    reference_distance_km: float | None = None
    reference_estimated_cost: float | None = None
    reference_justification: str | None
    reference_paired_unit_id: str | None = None
    reference_paired_unit_type: str | None = None
    reference_paired_role: str | None = None
    matches_reference_unit: bool
    matches_reference_type: bool
    matches_paired_unit: bool = False
    matches_paired_type: bool = False
    sla_target_min: int | None = None
    sla_met_core: bool | None = None
    sla_met_ref: bool | None = None
    eta_delta_min: float | None = None


class ScenarioEvaluationOut(BaseModel):
    scenario: ScenarioSummaryOut
    results: list[ScenarioRequestEvalOut]
    unit_match_rate: float
    type_match_rate: float
    paired_match_rate: float | None = None
    avg_eta_core_min: float | None = None
    avg_eta_ref_min: float | None = None
    eta_delta_min: float | None = None
    sla_core_pct: float | None = None
    sla_ref_pct: float | None = None
    events_applied: int = 0


class ScenarioBatchItemOut(BaseModel):
    id_escenario: str
    nombre: str
    objetivo_aprendizaje: str
    n_solicitudes: int
    events_applied: int
    unit_matches: int
    type_matches: int
    unit_match_rate: float
    type_match_rate: float
    paired_match_rate: float | None = None
    avg_eta_core_min: float | None = None
    avg_eta_ref_min: float | None = None
    eta_delta_min: float | None = None
    sla_core_pct: float
    sla_ref_pct: float
    avg_cost_core: float | None = None
    avg_cost_ref: float | None = None
    avg_dist_core_km: float | None = None
    avg_dist_ref_km: float | None = None


class AllScenariosTotalsOut(BaseModel):
    total_scenarios: int
    total_requests: int
    unit_matches: int
    type_matches: int
    unit_match_rate: float
    type_match_rate: float
    avg_eta_core_min: float | None = None
    avg_eta_ref_min: float | None = None
    eta_delta_min: float | None = None
    sla_core_pct: float
    sla_ref_pct: float
    sla_vital_core_pct: float
    sla_vital_ref_pct: float
    avg_cost_core: float | None = None
    avg_cost_ref: float | None = None
    avg_dist_core_km: float | None = None
    avg_dist_ref_km: float | None = None
    discrepancy_counts: dict[str, int]
    r01_incompatible_count: int
    r03_vital_without_ambulance_or_pair: int
    r04_stabilization_count: int
    r06_diversion_detected_count: int
    d03_green_uncovered_warnings: int
    d05_tam_on_02_warnings: int
    d06_transfer_tab_activations: int


class AllScenariosEvaluationOut(BaseModel):
    provenance: Literal["SIMULADO"] = "SIMULADO"
    scenarios: list[ScenarioBatchItemOut]
    totals: AllScenariosTotalsOut
