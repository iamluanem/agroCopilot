from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application import settings_service as svc
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", summary="Economic assumptions, risk thresholds and copilot provider")
def get(s: Session = Depends(get_session)):
    return svc.get_settings(s)


@router.put("", summary="Update settings (assessments are recomputed on demand)")
def put(data: svc.SettingsIn, s: Session = Depends(get_session)):
    return svc.save_settings(s, data)
