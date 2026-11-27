from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.simulation import (
    AdvanceClockIn,
    AdvanceClockOut,
    ArriveServiceOut,
    CompleteServiceIn,
    CompleteServiceOut,
    DivertUnitIn,
    DivertUnitOut,
    FlowInfoOut,
    FlowLoadIn,
    FlowStatusOut,
    GenerateRequestsIn,
    GenerateRequestsOut,
    PositionsBatchIn,
    PositionsBatchOut,
    ReclassifyServiceIn,
    ReclassifyServiceOut,
    ResetDemoOut,
    SimulationEvaluationOut,
    SimulationStateOut,
)
from app.services.flow_service import flow_status, list_flows, load_flow, unload_flow
from app.services.simulation_control_service import (
    advance_simulation_clock,
    arrive_service_in_simulation,
    complete_service_in_simulation,
    divert_unit_in_simulation,
    generate_random_requests,
    get_simulation_state,
    ingest_live_positions,
    reclassify_service_in_simulation,
    release_unit_in_simulation,
    reset_demo_session,
)
from app.services.simulation_evaluation_service import evaluate_simulation

router = APIRouter(prefix="/simulation", tags=["simulation"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/state", response_model=SimulationStateOut)
def simulation_state(db: DbDep) -> SimulationStateOut:
    return get_simulation_state(db)


@router.post("/positions", response_model=PositionsBatchOut)
def simulation_positions(payload: PositionsBatchIn, db: DbDep) -> PositionsBatchOut:
    return ingest_live_positions(db, payload)


@router.post("/arrive/{service_id}", response_model=ArriveServiceOut)
def simulation_arrive_service(service_id: str, db: DbDep) -> ArriveServiceOut:
    return arrive_service_in_simulation(db, service_id)


@router.post("/complete/{service_id}", response_model=CompleteServiceOut)
def simulation_complete_service(
    service_id: str,
    db: DbDep,
    payload: Annotated[CompleteServiceIn | None, Body()] = None,
) -> CompleteServiceOut:
    return complete_service_in_simulation(db, service_id, payload)


@router.post("/release/{service_id}", response_model=CompleteServiceOut)
def simulation_release_unit(service_id: str, db: DbDep) -> CompleteServiceOut:
    result = release_unit_in_simulation(db, service_id)
    db.commit()
    return result


@router.post("/advance-clock", response_model=AdvanceClockOut)
def simulation_advance_clock(payload: AdvanceClockIn, db: DbDep) -> AdvanceClockOut:
    return advance_simulation_clock(db, payload.minutes, live=payload.live)


@router.post("/generate", response_model=GenerateRequestsOut)
def simulation_generate_requests(
    db: DbDep,
    payload: Annotated[GenerateRequestsIn | None, Body()] = None,
) -> GenerateRequestsOut:
    return generate_random_requests(db, (payload.count if payload else 4))


@router.post("/reclassify/{service_id}", response_model=ReclassifyServiceOut)
def simulation_reclassify_service(
    service_id: str,
    payload: ReclassifyServiceIn,
    db: DbDep,
) -> ReclassifyServiceOut:
    return reclassify_service_in_simulation(db, service_id, payload)


@router.post("/divert", response_model=DivertUnitOut)
def simulation_divert_unit(
    payload: DivertUnitIn,
    db: DbDep,
) -> DivertUnitOut:
    return divert_unit_in_simulation(db, payload)


@router.get("/flows", response_model=list[FlowInfoOut])
def simulation_list_flows() -> list[FlowInfoOut]:
    return list_flows()


@router.get("/flow", response_model=FlowStatusOut)
def simulation_flow_status(db: DbDep) -> FlowStatusOut:
    return flow_status(db)


@router.post("/flow/load", response_model=FlowStatusOut)
def simulation_load_flow(payload: FlowLoadIn, db: DbDep) -> FlowStatusOut:
    return load_flow(db, payload.name)


@router.post("/flow/unload", response_model=FlowStatusOut)
def simulation_unload_flow(db: DbDep) -> FlowStatusOut:
    return unload_flow(db)


@router.post("/reset-demo", response_model=ResetDemoOut)
def simulation_reset_demo(db: DbDep) -> ResetDemoOut:
    return reset_demo_session(db)


@router.get("/evaluation", response_model=SimulationEvaluationOut)
def simulation_evaluation(
    db: DbDep, scope: Annotated[Literal["flow", "all"], Query()] = "flow"
) -> SimulationEvaluationOut:
    return evaluate_simulation(db, scope)
