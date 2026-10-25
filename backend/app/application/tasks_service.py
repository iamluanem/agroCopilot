from datetime import date

from pydantic import BaseModel, Field as PField
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.map_service import NotFound
from app.infrastructure.db.models import CropSeason, Field, MemoryEvent, RiskAssessment, Task


class TaskCreate(BaseModel):
    field_id: int
    assessment_id: int | None = None
    title: str = PField(min_length=3, max_length=160)
    kind: str = "vistoria"
    priority: str = PField(default="alta", pattern="^(alta|media|baixa)$")
    assignee: str | None = None
    due_date: date | None = None
    instructions: str | None = None
    source: str = PField(default="manual", description="manual | copiloto | mapa")


def task_dict(t: Task, field: Field) -> dict:
    return dict(id=t.id, field_id=t.field_id, field_code=field.code, field_name=field.name, assessment_id=t.assessment_id,
                title=t.title, kind=t.kind, priority=t.priority, assignee=t.assignee, due_date=t.due_date,
                instructions=t.instructions, status=t.status, created_at=t.created_at, is_synthetic=t.is_synthetic)


def create_task(s: Session, data: TaskCreate) -> dict:
    field = s.get(Field, data.field_id)
    if not field:
        raise NotFound("Talhão não encontrado")
    geom = None
    if data.assessment_id:
        ra = s.get(RiskAssessment, data.assessment_id)
        if not ra or ra.field_id != field.id:
            raise NotFound("Avaliação não encontrada para este talhão")
        geom = ra.geom
    t = Task(farm_id=field.farm_id, field_id=field.id, assessment_id=data.assessment_id, title=data.title,
             kind=data.kind, priority=data.priority, assignee=data.assignee, due_date=data.due_date,
             instructions=data.instructions, status="atribuída" if data.assignee else "pendente", geom=geom,
             is_synthetic=False)
    s.add(t)
    s.flush()
    season = s.scalars(select(CropSeason).where(CropSeason.farm_id == field.farm_id, CropSeason.is_current.is_(True))).first()
    ref = field.farm.reference_date
    s.add(MemoryEvent(field_id=field.id, season_id=season.id if season else None, date=ref, type="tarefa",
                      title=f"Vistoria criada: {data.title}",
                      summary=f"Origem: {data.source}. Responsável: {data.assignee or 'a definir'}. "
                              f"{data.instructions or ''}".strip(),
                      refs={"task_id": t.id, "assessment_id": data.assessment_id}, is_synthetic=False))
    s.commit()
    s.refresh(t)
    return task_dict(t, field)
