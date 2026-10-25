from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application import operations as ops
from app.application.map_service import NotFound
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api", tags=["operação"])


def _run(fn, *a):
    try:
        return fn(*a)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e
    except ops.InvalidOperation as e:
        raise HTTPException(422, str(e)) from e


@router.get("/tasks", summary="Lista tarefas")
def list_tasks(status: str | None = None, field_id: int | None = None, s: Session = Depends(get_session)):
    return ops.list_tasks(s, status, field_id)


@router.post("/tasks", status_code=201, summary="Cria tarefa (ex.: vistoria confirmada a partir do copiloto)")
def create(data: ops.TaskCreate, s: Session = Depends(get_session)):
    return _run(ops.create_task, s, data)


@router.get("/tasks/{task_id}", summary="Detalhe da tarefa com vistoria, intervenções e resultado")
def get(task_id: int, s: Session = Depends(get_session)):
    return _run(ops.get_task, s, task_id)


@router.patch("/tasks/{task_id}/status", summary="Muda status (fluxo controlado)")
def status(task_id: int, data: ops.StatusChange, s: Session = Depends(get_session)):
    return _run(ops.change_status, s, task_id, data.status)


@router.post("/tasks/{task_id}/inspection", summary="Registra vistoria de campo (achados, causa, fotos)")
def inspection(task_id: int, data: ops.InspectionIn, s: Session = Depends(get_session)):
    return _run(ops.record_inspection, s, task_id, data)


@router.post("/tasks/{task_id}/verify", summary="Verificação da vistoria por engenheiro agrônomo")
def verify(task_id: int, data: ops.VerifyIn, s: Session = Depends(get_session)):
    return _run(ops.verify_task, s, task_id, data)


@router.post("/interventions", status_code=201, summary="Registra intervenção aprovada e executada")
def intervention(data: ops.InterventionIn, s: Session = Depends(get_session)):
    return _run(ops.create_intervention, s, data)


@router.post("/interventions/{intervention_id}/simulate",
             summary="DEMO: gera observações pós-intervenção sintéticas e mede o resultado")
def simulate(intervention_id: int, s: Session = Depends(get_session)):
    return _run(ops.simulate_and_measure, s, intervention_id)


@router.get("/outcomes", summary="Resultados de intervenções")
def outcomes(s: Session = Depends(get_session)):
    return ops.list_outcomes(s)


@router.get("/outcomes/{outcome_id}", summary="Relatório de resultado: antes/depois, comparação, limitações")
def outcome(outcome_id: int, s: Session = Depends(get_session)):
    return _run(ops.outcome_detail, s, outcome_id)


@router.post("/demo/reset", summary="Remove tarefas, intervenções e simulações criadas na demonstração")
def reset(s: Session = Depends(get_session)):
    return ops.reset_demo(s)
