from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application.map_service import NotFound
from app.application.tasks_service import TaskCreate, create_task
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api/tasks", tags=["tarefas"])


@router.post("", status_code=201, summary="Cria tarefa (ex.: vistoria confirmada a partir do copiloto)")
def create(data: TaskCreate, s: Session = Depends(get_session)):
    try:
        return create_task(s, data)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e
