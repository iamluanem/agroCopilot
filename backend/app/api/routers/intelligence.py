from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application import intelligence as svc
from app.application.map_service import NotFound
from app.infrastructure.db.base import get_session
from app.infrastructure.db.models import Farm

router = APIRouter(prefix="/api", tags=["intelligence"])


def _ref(s: Session, farm_id: int, on: date | None) -> date:
    farm = s.get(Farm, farm_id)
    if not farm:
        raise HTTPException(404, "Farm not found")
    return on or farm.reference_date


@router.get("/farms/{farm_id}/priorities", summary="Fields ranked by exposure × urgency × confidence")
def priorities(farm_id: int, on: date | None = None, s: Session = Depends(get_session)):
    try:
        return svc.priorities(s, farm_id, _ref(s, farm_id, on))
    except NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/fields/{field_id}/assessment", summary="Affected zone, hypotheses and R$ exposure for a field")
def assessment(field_id: int, on: date, s: Session = Depends(get_session)):
    try:
        return svc.assess_field(s, field_id, on)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/fields/{field_id}", summary="Field detail: assessment, evolution, weather and memory")
def field_detail(field_id: int, on: date | None = None, s: Session = Depends(get_session)):
    try:
        return svc.field_detail(s, field_id, on)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/fields/{field_id}/memory", summary="Field agronomic memory (optional text search)")
def memory(field_id: int, q: str | None = None, s: Session = Depends(get_session)):
    return svc.memory(s, field_id, q)


@router.get("/farms/{farm_id}/weather", summary="Daily weather (synthetic)")
def weather(farm_id: int, start: date, end: date, s: Session = Depends(get_session)):
    return svc.weather(s, farm_id, start, end)


@router.get("/farms/{farm_id}/tasks/summary", summary="Task count by status")
def tasks_summary(farm_id: int, s: Session = Depends(get_session)):
    from sqlalchemy import func, select

    from app.infrastructure.db.models import Task
    rows = dict(s.execute(select(Task.status, func.count()).where(Task.farm_id == farm_id).group_by(Task.status)).all())
    open_ = sum(v for k, v in rows.items() if k not in ("completed", "verified"))
    return {"by_status": rows, "open": open_}
