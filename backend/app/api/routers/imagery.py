import json

from fastapi import APIRouter

from app.application.operations import MEDIA_DIR

router = APIRouter(prefix="/api", tags=["imagens"])


@router.get("/farms/{farm_id}/imagery", summary="Cenas Sentinel-2 reais processadas (scripts/fetch_sentinel.py)")
def imagery(farm_id: int):
    out = []
    for f in sorted((MEDIA_DIR / "sentinel").glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if rec.get("farm_id") in (None, farm_id):
            out.append(rec)
    return sorted(out, key=lambda r: r.get("date", ""), reverse=True)
