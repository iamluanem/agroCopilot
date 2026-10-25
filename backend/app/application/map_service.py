"""Casos de uso de leitura do mapa: fazenda, talhões, células, datas e snapshot de risco."""
from datetime import date
from functools import lru_cache

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.risk import CONFIDENCE, LEVELS, RiskThresholds, compute_cell_risk, field_level
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import AppSetting, CropSeason, Farm, Field


class NotFound(Exception):
    pass


def _thresholds(s: Session) -> RiskThresholds:
    cfg = s.get(AppSetting, "risco")
    v = cfg.value if cfg else {}
    return RiskThresholds(
        yellow=float(v.get("limiar_amarelo", 1.5)),
        red=float(v.get("limiar_vermelho", 2.5)),
        weight_hist=float(v.get("peso_historico", 0.6)),
    )


def list_farms(s: Session) -> list[dict]:
    return [
        dict(id=f.id, name=f.name, municipality=f.municipality, state=f.state, crop=f.crop,
             area_ha=f.area_ha, is_synthetic=f.is_synthetic)
        for f in s.scalars(select(Farm).order_by(Farm.id))
    ]


def get_farm(s: Session, farm_id: int) -> dict:
    farm = s.get(Farm, farm_id)
    if not farm:
        raise NotFound("Fazenda não encontrada")
    bbox = s.execute(text(
        "SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e) FROM (SELECT ST_Extent(geom) e FROM fields WHERE farm_id=:f) x"
    ), {"f": farm_id}).one()
    return dict(
        id=farm.id, name=farm.name, municipality=farm.municipality, state=farm.state, crop=farm.crop,
        area_ha=farm.area_ha, reference_date=farm.reference_date, soil_notes=farm.soil_notes,
        is_synthetic=farm.is_synthetic, bbox=list(bbox),
        seasons=[dict(id=x.id, name=x.name, sowing_date=x.sowing_date, harvest_date=x.harvest_date,
                      is_current=x.is_current, expected_yield_sc_ha=x.expected_yield_sc_ha,
                      realized_yield_sc_ha=x.realized_yield_sc_ha) for x in farm.seasons],
        fields=[dict(id=f.id, code=f.code, name=f.name, area_ha=f.area_ha) for f in farm.fields],
    )


def fields_geojson(s: Session, farm_id: int) -> str:
    return s.execute(text("""
        SELECT json_build_object('type','FeatureCollection','features', COALESCE(json_agg(json_build_object(
          'type','Feature','id',f.id,'geometry',ST_AsGeoJSON(f.geom,6)::json,
          'properties',json_build_object('id',f.id,'code',f.code,'name',f.name,'area_ha',f.area_ha,
             'soil_texture',f.soil_texture,'irrigation',f.irrigation,'boundary_source',f.boundary_source,
             'is_synthetic',f.is_synthetic,
             'label_point',ST_AsGeoJSON(ST_PointOnSurface(f.geom),6)::json->'coordinates')
        ) ORDER BY f.code), '[]'::json))::text
        FROM fields f WHERE f.farm_id=:f
    """), {"f": farm_id}).scalar_one()


def cells_geojson(s: Session, farm_id: int) -> str:
    return s.execute(text("""
        SELECT json_build_object('type','FeatureCollection','features', COALESCE(json_agg(json_build_object(
          'type','Feature','id',c.id,'geometry',ST_AsGeoJSON(c.geom,6)::json,
          'properties',json_build_object('f',c.field_id,'a',c.area_ha)) ORDER BY c.id), '[]'::json))::text
        FROM management_cells c JOIN fields f ON f.id=c.field_id WHERE f.farm_id=:f
    """), {"f": farm_id}).scalar_one()


def _current_season(s: Session, farm_id: int, on: date | None = None) -> CropSeason:
    q = select(CropSeason).where(CropSeason.farm_id == farm_id)
    if on:
        q = q.where(CropSeason.sowing_date <= on).order_by(CropSeason.sowing_date.desc())
    else:
        q = q.where(CropSeason.is_current.is_(True))
    season = s.scalars(q.limit(1)).first()
    if not season:
        raise NotFound("Safra não encontrada")
    return season


def observation_dates(s: Session, farm_id: int, season_id: int | None) -> list[dict]:
    season = s.get(CropSeason, season_id) if season_id else _current_season(s, farm_id)
    if not season or season.farm_id != farm_id:
        raise NotFound("Safra não encontrada")
    rows = s.execute(text("""
        SELECT date, das, avg(cloud_flag::int) AS cloud, bool_or(source = 'simulacao_pos_intervencao') AS sim
        FROM observations WHERE season_id=:s GROUP BY date, das ORDER BY date
    """), {"s": season.id}).all()
    return [dict(date=r.date, das=r.das, cloud_pct=round(float(r.cloud) * 100, 1), simulated=bool(r.sim),
                 source="Simulação pós-intervenção (demo)" if r.sim else "Dados de demonstração", season_id=season.id)
            for r in rows]


def risk_snapshot(farm_id: int, on: date) -> dict:
    with SessionLocal() as s:
        t = _thresholds(s)
    return _risk_snapshot_cached(farm_id, on, t)


def clear_cache() -> None:
    _risk_snapshot_cached.cache_clear()


@lru_cache(maxsize=160)
def _risk_snapshot_cached(farm_id: int, on: date, t: RiskThresholds) -> dict:
    with SessionLocal() as s:
        season = _current_season(s, farm_id, on)
        cur = s.execute(text("""
            SELECT o.cell_id, c.field_id, c.area_ha, o.ndvi, o.ndre, o.cloud_flag, o.das, o.source
            FROM observations o JOIN management_cells c ON c.id=o.cell_id
            WHERE o.season_id=:s AND o.date=:d ORDER BY o.cell_id
        """), {"s": season.id, "d": on}).all()
        if not cur:
            raise NotFound("Sem observações nesta data")
        das = cur[0].das
        base = dict(s.execute(text("""
            SELECT o.cell_id, avg(o.ndvi) FROM observations o JOIN crop_seasons cs ON cs.id=o.season_id
            WHERE cs.farm_id=:f AND cs.sowing_date < :sow AND o.das=:das AND NOT o.cloud_flag
            GROUP BY o.cell_id
        """), {"f": farm_id, "sow": season.sowing_date, "das": das}).all())
        recent = dict(s.execute(text("""
            SELECT cell_id, count(*) FILTER (WHERE NOT cloud_flag) FROM observations
            WHERE season_id=:s AND date > :d - 15 AND date <= :d GROUP BY cell_id
        """), {"s": season.id, "d": on}).all())
        fields = {f.id: f for f in s.scalars(select(Field).where(Field.farm_id == farm_id))}

    ids = np.array([r.cell_id for r in cur])
    fid = np.array([r.field_id for r in cur])
    area = np.array([r.area_ha for r in cur])
    ndvi = np.array([r.ndvi for r in cur], dtype=float)
    ndre = np.array([np.nan if r.ndre is None else r.ndre for r in cur], dtype=float)
    cloud = np.array([r.cloud_flag for r in cur])
    baseline = np.array([base.get(i, np.nan) for i in ids], dtype=float)
    rv = np.array([recent.get(i, 0) for i in ids])

    risk = compute_cell_risk(ndvi, baseline, fid, cloud, rv, t)

    def r(x, nd):
        return [None if not np.isfinite(v) else round(float(v), nd) for v in x]

    field_summ = []
    for f_id, f in sorted(fields.items(), key=lambda kv: kv[1].code):
        m = fid == f_id
        valid = m & ~cloud
        by_level = {lvl: round(float(area[m & (risk.level == i)].sum()), 1) for i, lvl in enumerate(LEVELS)}
        field_summ.append(dict(
            field_id=f_id, code=f.code, name=f.name, area_ha=f.area_ha,
            level=field_level(by_level), area_by_level=by_level,
            ndvi_mean=round(float(ndvi[valid].mean()), 3) if valid.any() else None,
            ndvi_baseline=round(float(np.nanmean(baseline[m])), 3) if np.isfinite(baseline[m]).any() else None,
            max_score=round(float(np.nanmax(risk.score[valid])), 2) if valid.any() else None,
            cloud_pct=round(float(cloud[m].mean()) * 100, 1),
        ))
    order = {"vermelho": 0, "amarelo": 1, "verde": 2}
    field_summ.sort(key=lambda x: (order[x["level"]], -(x["area_by_level"]["vermelho"] + x["area_by_level"]["amarelo"])))

    total = float(area.sum())
    farm_by_level = {lvl: round(float(area[risk.level == i].sum()), 1) for i, lvl in enumerate(LEVELS)}
    return dict(
        date=on, das=das, season_id=season.id, season_name=season.name, is_synthetic=True,
        simulated=cur[0].source == "simulacao_pos_intervencao",
        source="Simulação pós-intervenção (demo)" if cur[0].source == "simulacao_pos_intervencao" else "Dados de demonstração",
        method="z-score robusto do NDVI vs. histórico da célula no mesmo DAS (descontada a variação geral da "
               f"fazenda) e vs. mediana do talhão; score = -({t.weight_hist:.1f}·z_hist + {1 - t.weight_hist:.1f}·z_talhão). "
               f"Amarelo ≥ {t.yellow}, vermelho ≥ {t.red}. Observações com nuvem descartadas.",
        thresholds=dict(yellow=t.yellow, red=t.red),
        levels=list(LEVELS), confidence_labels=list(CONFIDENCE),
        cells=dict(
            id=ids.tolist(), level=risk.level.tolist(), score=r(risk.score, 2),
            ndvi=r(np.where(cloud, np.nan, ndvi), 3), ndre=r(np.where(cloud, np.nan, ndre), 3),
            baseline=r(baseline, 3), confidence=risk.confidence.tolist(), area=r(area, 3),
        ),
        fields=field_summ,
        summary=dict(
            total_ha=round(total, 1), area_by_level=farm_by_level,
            pct_by_level={k: round(v / total * 100, 1) for k, v in farm_by_level.items()},
            cloud_pct=round(float(cloud.mean()) * 100, 1),
        ),
    )


def field_series(s: Session, field_id: int) -> dict:
    field = s.get(Field, field_id)
    if not field:
        raise NotFound("Talhão não encontrado")
    rows = s.execute(text("""
        SELECT cs.id season_id, cs.name season, cs.is_current, o.date, o.das,
               avg(o.ndvi) FILTER (WHERE NOT o.cloud_flag) ndvi,
               avg(o.cloud_flag::int) cloud
        FROM observations o JOIN management_cells c ON c.id=o.cell_id JOIN crop_seasons cs ON cs.id=o.season_id
        WHERE c.field_id=:f GROUP BY cs.id, cs.name, cs.is_current, o.date, o.das ORDER BY cs.sowing_date, o.das
    """), {"f": field_id}).all()
    seasons: dict[str, dict] = {}
    for r in rows:
        ss = seasons.setdefault(r.season, dict(season_id=r.season_id, season=r.season, is_current=r.is_current, points=[]))
        ss["points"].append(dict(date=r.date, das=r.das, ndvi=None if r.ndvi is None else round(float(r.ndvi), 3),
                                 cloud_pct=round(float(r.cloud) * 100, 1)))
    return dict(field_id=field.id, code=field.code, name=field.name, is_synthetic=True,
                seasons=list(seasons.values()))
