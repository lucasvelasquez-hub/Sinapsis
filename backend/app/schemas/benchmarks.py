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
    matches_reference_unit: bool
    matches_reference_type: bool


class ScenarioEvaluationOut(BaseModel):
    scenario: ScenarioSummaryOut
    results: list[ScenarioRequestEvalOut]
    unit_match_rate: float
    type_match_rate: float
    events_applied: int = 0
