from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application import settings_service as svc
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api/settings", tags=["configurações"])


@router.get("", summary="Premissas econômicas, limiares de risco e provedor do copiloto")
def get(s: Session = Depends(get_session)):
    return svc.get_settings(s)


@router.put("", summary="Atualiza configurações (recalcula avaliações sob demanda)")
def put(data: svc.SettingsIn, s: Session = Depends(get_session)):
    return svc.save_settings(s, data)
