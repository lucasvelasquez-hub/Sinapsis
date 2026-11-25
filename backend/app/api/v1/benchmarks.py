from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.benchmarks import (
    AllScenariosEvaluationOut,
    KpisOverviewOut,
    ScenarioEvaluationOut,
    ScenarioSummaryOut,
)
from app.services.benchmarks_service import (
    evaluate_all_scenarios,
    evaluate_scenario,
    get_kpis_overview,
    list_scenarios,
)

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/kpis", response_model=KpisOverviewOut)
def kpis_overview(db: DbDep) -> KpisOverviewOut:
    return get_kpis_overview(db)


@router.get("/scenarios", response_model=list[ScenarioSummaryOut])
def scenarios_list() -> list[ScenarioSummaryOut]:
    return list_scenarios()


@router.post("/scenarios/evaluate-all", response_model=AllScenariosEvaluationOut)
def scenarios_evaluate_all(db: DbDep) -> AllScenariosEvaluationOut:
    return evaluate_all_scenarios(db)


@router.post("/scenarios/{scenario_id}/evaluate", response_model=ScenarioEvaluationOut)
def scenario_evaluate(scenario_id: str, db: DbDep) -> ScenarioEvaluationOut:
    return evaluate_scenario(db, scenario_id)
