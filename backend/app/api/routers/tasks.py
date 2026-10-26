from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application import operations as ops
from app.application.map_service import NotFound
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api", tags=["operations"])


def _run(fn, *a):
    try:
        return fn(*a)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e
    except ops.InvalidOperation as e:
        raise HTTPException(422, str(e)) from e


@router.get("/tasks", summary="List tasks")
def list_tasks(status: str | None = None, field_id: int | None = None, s: Session = Depends(get_session)):
    return ops.list_tasks(s, status, field_id)


@router.post("/tasks", status_code=201, summary="Create a task (e.g. an inspection confirmed from the copilot)")
def create(data: ops.TaskCreate, s: Session = Depends(get_session)):
    return _run(ops.create_task, s, data)


@router.get("/tasks/{task_id}", summary="Task detail with inspection, interventions and outcome")
def get(task_id: int, s: Session = Depends(get_session)):
    return _run(ops.get_task, s, task_id)


@router.patch("/tasks/{task_id}/status", summary="Change status (controlled workflow)")
def status(task_id: int, data: ops.StatusChange, s: Session = Depends(get_session)):
    return _run(ops.change_status, s, task_id, data.status)


@router.post("/tasks/{task_id}/inspection", summary="Record a field inspection (findings, cause, photos)")
def inspection(task_id: int, data: ops.InspectionIn, s: Session = Depends(get_session)):
    return _run(ops.record_inspection, s, task_id, data)


@router.post("/tasks/{task_id}/verify", summary="Inspection verification by a licensed agronomist")
def verify(task_id: int, data: ops.VerifyIn, s: Session = Depends(get_session)):
    return _run(ops.verify_task, s, task_id, data)


@router.post("/interventions", status_code=201, summary="Record an approved, executed intervention")
def intervention(data: ops.InterventionIn, s: Session = Depends(get_session)):
    return _run(ops.create_intervention, s, data)


@router.post("/interventions/{intervention_id}/simulate",
             summary="DEMO: generate synthetic post-intervention observations and measure the outcome")
def simulate(intervention_id: int, s: Session = Depends(get_session)):
    return _run(ops.simulate_and_measure, s, intervention_id)


@router.get("/outcomes", summary="Intervention outcomes")
def outcomes(s: Session = Depends(get_session)):
    return ops.list_outcomes(s)


@router.get("/outcomes/{outcome_id}", summary="Outcome report: before/after, comparison, limitations")
def outcome(outcome_id: int, s: Session = Depends(get_session)):
    return _run(ops.outcome_detail, s, outcome_id)


@router.post("/demo/reset", summary="Remove tasks, interventions and simulations created during the demo")
def reset(s: Session = Depends(get_session)):
    return ops.reset_demo(s)
