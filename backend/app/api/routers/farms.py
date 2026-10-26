from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.application import map_service as svc
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api", tags=["map"])
GEOJSON = "application/geo+json"


def _nf(fn, *a):
    try:
        return fn(*a)
    except svc.NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/farms", summary="List farms")
def farms(s: Session = Depends(get_session)):
    return svc.list_farms(s)


@router.get("/farms/{farm_id}", summary="Farm detail, seasons and bbox")
def farm(farm_id: int, s: Session = Depends(get_session)):
    return _nf(svc.get_farm, s, farm_id)


@router.get("/farms/{farm_id}/fields.geojson", summary="Fields (GeoJSON)")
def fields(farm_id: int, s: Session = Depends(get_session)):
    return Response(svc.fields_geojson(s, farm_id), media_type=GEOJSON)


@router.get("/farms/{farm_id}/cells.geojson", summary="Management cells (GeoJSON)")
def cells(farm_id: int, s: Session = Depends(get_session)):
    return Response(svc.cells_geojson(s, farm_id), media_type=GEOJSON,
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/farms/{farm_id}/dates", summary="Observation dates in the season (with cloud %)")
def dates(farm_id: int, season_id: int | None = None, s: Session = Depends(get_session)):
    return _nf(svc.observation_dates, s, farm_id, season_id)


@router.get("/farms/{farm_id}/risk", summary="Per-cell and per-field risk snapshot on a date")
def risk(farm_id: int, on: date):
    return _nf(svc.risk_snapshot, farm_id, on)


@router.get("/fields/{field_id}/series", summary="Field mean NDVI series by season")
def series(field_id: int, s: Session = Depends(get_session)):
    return _nf(svc.field_series, s, field_id)
