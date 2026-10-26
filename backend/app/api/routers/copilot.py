from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application import copilot_service as svc
from app.domain.copilot import CopilotRequest, CopilotResponse
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.get("/status", summary="Active provider and suggested questions")
def status(s: Session = Depends(get_session)):
    return svc.status(s)


@router.post("/ask", response_model=CopilotResponse, summary="Ask the copilot (structured answer)")
def ask(req: CopilotRequest, s: Session = Depends(get_session)):
    try:
        return svc.ask(s, req)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
