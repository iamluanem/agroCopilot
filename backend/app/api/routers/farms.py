from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.application import map_service as svc
from app.infrastructure.db.base import get_session

router = APIRouter(prefix="/api", tags=["mapa"])
GEOJSON = "application/geo+json"


def _nf(fn, *a):
    try:
        return fn(*a)
    except svc.NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/farms", summary="Lista fazendas")
def farms(s: Session = Depends(get_session)):
    return svc.list_farms(s)


@router.get("/farms/{farm_id}", summary="Detalhe da fazenda, safras e bbox")
def farm(farm_id: int, s: Session = Depends(get_session)):
    return _nf(svc.get_farm, s, farm_id)


@router.get("/farms/{farm_id}/fields.geojson", summary="Talhões (GeoJSON)")
def fields(farm_id: int, s: Session = Depends(get_session)):
    return Response(svc.fields_geojson(s, farm_id), media_type=GEOJSON)


@router.get("/farms/{farm_id}/cells.geojson", summary="Células de manejo (GeoJSON)")
def cells(farm_id: int, s: Session = Depends(get_session)):
    return Response(svc.cells_geojson(s, farm_id), media_type=GEOJSON,
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/farms/{farm_id}/dates", summary="Datas com observação na safra (com % de nuvem)")
def dates(farm_id: int, season_id: int | None = None, s: Session = Depends(get_session)):
    return _nf(svc.observation_dates, s, farm_id, season_id)


@router.get("/farms/{farm_id}/risk", summary="Snapshot de risco por célula e talhão numa data")
def risk(farm_id: int, on: date):
    return _nf(svc.risk_snapshot, farm_id, on)


@router.get("/fields/{field_id}/series", summary="Série de NDVI médio do talhão por safra")
def series(field_id: int, s: Session = Depends(get_session)):
    return _nf(svc.field_series, s, field_id)
