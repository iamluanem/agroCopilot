"""Per-field risk assessment: affected zone, hypotheses, R$ exposure and priority.

Assessments are materialized in risk_assessments / hypotheses / economic_estimates so that tasks, the copilot and
reports all reference the same auditable record.
"""
import hashlib
import json
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.application.map_service import NotFound, observation_dates, risk_snapshot
from app.core.fmt import num
from app.domain import economics as eco
from app.domain.hypotheses import PATTERN_LABEL, ZoneContext, classify_pattern, rank_hypotheses, recommended_next_step
from app.domain.risk import CONFIDENCE, LEVEL_CODE
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import (
    AppSetting, CropSeason, EconomicEstimate, Field, Hypothesis, Inspection, MemoryEvent, RiskAssessment, Task,
    WeatherDaily,
)

MIN_AFFECTED_HA = 1.0
METHOD = "risk-v1 · rule-hypotheses-v1 · economics-v1"
YELLOW, RED = LEVEL_CODE["yellow"], LEVEL_CODE["red"]


def get_assumptions(s: Session) -> eco.EconomicAssumptions:
    row = s.get(AppSetting, "economics")
    return eco.EconomicAssumptions.from_dict(row.value if row else None)


def _settings_hash(s: Session) -> str:
    rows = {r.key: r.value for r in s.scalars(select(AppSetting).where(AppSetting.key.in_(("economics", "risk"))))}
    return hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:12]


@lru_cache(maxsize=4)
def _cell_layout(farm_id: int) -> dict[int, tuple[int, int, int]]:
    with SessionLocal() as s:
        rows = s.execute(text("""
            SELECT c.id, c.field_id, c.row, c.col FROM management_cells c JOIN fields f ON f.id=c.field_id
            WHERE f.farm_id=:f
        """), {"f": farm_id}).all()
    return {r.id: (r.field_id, r.row, r.col) for r in rows}


def _season_snapshots(s: Session, farm_id: int, season_id: int, until: date | None = None) -> list[dict]:
    out = []
    for d in observation_dates(s, farm_id, season_id):
        if until and d["date"] > until:
            break
        out.append(risk_snapshot(farm_id, d["date"]))
    return out


def _weather_context(s: Session, farm_id: int, on: date, sowing: date) -> dict:
    rows = s.scalars(select(WeatherDaily).where(
        WeatherDaily.farm_id == farm_id, WeatherDaily.date > on - timedelta(days=30), WeatherDaily.date <= on,
    ).order_by(WeatherDaily.date)).all()
    best, cur, best_end = 0, 0, None
    for i, w in enumerate(rows):
        cur = cur + 1 if w.rain_mm < 2 else 0
        if cur > best:
            best, best_end = cur, i
    dry = rows[best_end - best + 1: best_end + 1] if best_end is not None else []
    return dict(
        max_dry_days=best,
        dry_start=dry[0].date if dry else None,
        dry_end=dry[-1].date if dry else None,
        dry_start_das=(dry[0].date - sowing).days if dry else None,
        tmax_dry_mean=float(np.mean([w.tmax_c for w in dry])) if dry else None,
        rain_21d_mm=round(sum(w.rain_mm for w in rows if w.date > on - timedelta(days=21)), 1),
    )


def _zone_mask(snap: dict, field_id: int, layout: dict) -> tuple[np.ndarray, np.ndarray]:
    ids = np.asarray(snap["cells"]["id"])
    lvl = np.asarray(snap["cells"]["level"])
    fmask = np.array([layout[i][0] == field_id for i in ids])
    return fmask, fmask & ((lvl == YELLOW) | (lvl == RED))


def _onset(field_id: int, zone_ids: set[int], snaps: list[dict]) -> int | None:
    """First DAS from which ≥30% of the current zone is anomalous in every subsequent valid observation."""
    fracs = []
    for sn in snaps:
        ids, lvl = sn["cells"]["id"], sn["cells"]["level"]
        z = [l for i, l in zip(ids, lvl) if i in zone_ids]
        valid = [l for l in z if l != LEVEL_CODE["no_data"]]
        fracs.append((sn["das"], None if len(valid) < 0.5 * len(z) else np.mean([l in (YELLOW, RED) for l in valid])))
    onset = None
    for das, f in reversed(fracs):
        if f is None:
            continue
        if f >= 0.3:
            onset = das
        else:
            break
    return onset


def _recurrence(farm_id: int, zone_ids: set[int], prev_snaps: list[dict]) -> float:
    best = 0.0
    for sn in prev_snaps:
        hit = [l in (YELLOW, RED) for i, l in zip(sn["cells"]["id"], sn["cells"]["level"]) if i in zone_ids]
        if hit:
            best = max(best, float(np.mean(hit)))
    return round(best, 2)


def _prior_verified(s: Session, field_id: int, before: date) -> list[tuple[str, str]]:
    rows = s.execute(
        select(CropSeason.name, Inspection.verified_cause)
        .join(Task, Task.id == Inspection.task_id)
        .join(CropSeason, (CropSeason.farm_id == Task.farm_id) & (CropSeason.sowing_date <= Inspection.inspected_at)
              & ((CropSeason.harvest_date.is_(None)) | (CropSeason.harvest_date >= Inspection.inspected_at)))
        .where(Task.field_id == field_id, Inspection.verified_cause.is_not(None), Inspection.inspected_at < before)
        .order_by(Inspection.inspected_at.desc())
    ).all()
    return [(r[0], r[1]) for r in rows]


def assess_field(s: Session, field_id: int, on: date) -> dict:
    field = s.get(Field, field_id)
    if not field:
        raise NotFound("Field not found")
    snap = risk_snapshot(field.farm_id, on)
    layout = _cell_layout(field.farm_id)
    fmask, zmask = _zone_mask(snap, field_id, layout)
    area = np.asarray(snap["cells"]["area"])
    lvl = np.asarray(snap["cells"]["level"])
    red_ha = float(area[zmask & (lvl == RED)].sum())
    yellow_ha = float(area[zmask & (lvl == YELLOW)].sum())
    fsum = next(f for f in snap["fields"] if f["field_id"] == field_id)
    a = get_assumptions(s)

    base = dict(field_id=field.id, code=field.code, name=field.name, area_ha=field.area_ha, date=on,
                das=snap["das"], stage=eco.soybean_stage(snap["das"]), level=fsum["level"],
                red_ha=round(red_ha, 1), yellow_ha=round(yellow_ha, 1), is_synthetic=True,
                ndvi_mean=fsum["ndvi_mean"], ndvi_baseline=fsum["ndvi_baseline"])
    if fsum["level"] == "green" or red_ha + yellow_ha < MIN_AFFECTED_HA:
        return {**base, "assessment_id": None, "has_zone": False, "priority_score": 0.0,
                "summary": f"No relevant anomaly zone on this date ({num(red_ha + yellow_ha, 1)} ha of isolated cells, within normal variation).", "hypotheses": [], "economics": None}

    h = _settings_hash(s)
    # assessments are versioned by assumptions: changing Settings creates a new version and keeps the old ones,
    # which remain referenced by tasks and outcomes already created
    existing = next((r for r in s.scalars(select(RiskAssessment).where(
        RiskAssessment.field_id == field_id, RiskAssessment.date == on, RiskAssessment.cell_id.is_(None),
    ).order_by(RiskAssessment.id.desc())) if r.details.get("settings_hash") == h), None)
    if existing:
        return _to_dict(s, existing, base)

    season = s.get(CropSeason, snap["season_id"])
    ids = np.asarray(snap["cells"]["id"])
    zone_ids = set(ids[zmask].tolist())
    rows = np.array([layout[i][1] for i in ids[zmask]])
    cols = np.array([layout[i][2] for i in ids[zmask]])
    pattern, cluster_share = classify_pattern(rows, cols)

    snaps = _season_snapshots(s, field.farm_id, season.id, until=on)
    onset = _onset(field_id, zone_ids, snaps)
    prev = s.scalars(select(CropSeason).where(
        CropSeason.farm_id == field.farm_id, CropSeason.sowing_date < season.sowing_date,
    ).order_by(CropSeason.sowing_date.desc())).first()
    recurrence = _recurrence(field.farm_id, zone_ids, _season_snapshots(s, field.farm_id, prev.id)) if prev else 0.0

    wx = _weather_context(s, field.farm_id, on, season.sowing_date)
    ndvi = np.asarray([np.nan if v is None else v for v in snap["cells"]["ndvi"]], dtype=float)
    basel = np.asarray([np.nan if v is None else v for v in snap["cells"]["baseline"]], dtype=float)
    drop = float(np.nanmean(ndvi[zmask] - basel[zmask]))
    notes = [m.summary for m in s.scalars(select(MemoryEvent).where(
        MemoryEvent.field_id == field_id, MemoryEvent.season_id == season.id, MemoryEvent.type == "note"))]

    ctx = ZoneContext(
        red_ha=red_ha, yellow_ha=yellow_ha, das=snap["das"], stage=eco.soybean_stage(snap["das"]),
        pattern=pattern, onset_das=onset, ndvi_drop=drop, max_dry_days=wx["max_dry_days"],
        rain_21d_mm=wx["rain_21d_mm"], tmax_dry_mean=wx["tmax_dry_mean"], soil_texture=field.soil_texture,
        irrigation=field.irrigation, recurrence_share=recurrence, dry_start_das=wx["dry_start_das"],
        prior_verified=_prior_verified(s, field_id, on), field_notes=notes,
    )
    hyps = rank_hypotheses(ctx)

    # trend: anomalous area in the previous valid observations
    hist = [(sn["das"], next(f for f in sn["fields"] if f["field_id"] == field_id)) for sn in snaps[:-1]]
    hist = [(d, f["area_by_level"]["red"] + f["area_by_level"]["yellow"]) for d, f in hist if f["cloud_pct"] < 30]
    worsening = len(hist) >= 1 and (red_ha + yellow_ha) > hist[-1][1] * 1.15 + 1
    urg, urg_why = eco.urgency(snap["das"], worsening)

    conf_codes = np.asarray(snap["cells"]["confidence"])[zmask]
    conf_codes = conf_codes[conf_codes >= 0]
    risk_conf = CONFIDENCE[int(np.round(np.median(conf_codes)))] if conf_codes.size else "baixa"
    exp = eco.estimate_exposure(red_ha, yellow_ha, a)
    mid = (exp.exposure_min + exp.exposure_max) / 2
    prio = eco.priority_score(mid, urg, risk_conf)

    geom_wkt = s.execute(text(
        "SELECT ST_AsEWKT(ST_Multi(ST_Union(geom))) FROM management_cells WHERE id = ANY(:ids)"
    ), {"ids": list(map(int, zone_ids))}).scalar_one()

    observation = (
        f"Zone NDVI {num(abs(drop), 2)} {'below' if drop < 0 else 'above'} the area's own history at the same stage, "
        f"across {num(red_ha, 1)} critical ha and {num(yellow_ha, 1)} watch ha ({PATTERN_LABEL[pattern]})."
    )
    ra = RiskAssessment(
        field_id=field_id, cell_id=None, date=on, level=fsum["level"], anomaly_score=float(fsum["max_score"] or 0),
        confidence=risk_conf, method=METHOD, affected_ha=exp.affected_ha, geom=geom_wkt, is_synthetic=True,
        details=dict(
            settings_hash=h, observation=observation, pattern=pattern, pattern_label=PATTERN_LABEL[pattern],
            cluster_share=round(cluster_share, 2), onset_das=onset,
            onset_date=str(season.sowing_date + timedelta(days=onset)) if onset is not None else None,
            ndvi_drop=round(drop, 3), recurrence_share=recurrence, weather={k: (str(v) if isinstance(v, date) else v)
                                                                          for k, v in wx.items()},
            urgency=urg, urgency_reason=urg_why, worsening=worsening, priority_score=prio,
            priority_formula=eco.PRIORITY_FORMULA, stage=ctx.stage,
            next_step=recommended_next_step(hyps[0], red_ha),
            prior_verified=[{"season": a_, "cause": c} for a_, c in ctx.prior_verified],
        ),
    )
    s.add(ra)
    s.flush()
    for i, hy in enumerate(hyps, 1):
        s.add(Hypothesis(assessment_id=ra.id, rank=i, cause=hy.cause, confidence=hy.confidence,
                         supporting_evidence=hy.evidence, missing_data=hy.missing))
    s.add(EconomicEstimate(
        assessment_id=ra.id, affected_ha=exp.affected_ha, exposure_min=exp.exposure_min, exposure_max=exp.exposure_max,
        inspection_cost=exp.inspection_cost, intervention_cost=exp.intervention_cost,
        assumptions={**exp.assumptions, "formula": exp.formula, "gross_value_brl": exp.gross_value_brl,
                     "hypothesis_scores": {hy.key: round(hy.score, 2) for hy in hyps}},
    ))
    s.commit()
    s.refresh(ra)
    return _to_dict(s, ra, base)


def _to_dict(s: Session, ra: RiskAssessment, base: dict) -> dict:
    est = s.scalars(select(EconomicEstimate).where(EconomicEstimate.assessment_id == ra.id)).first()
    d = ra.details
    a = dict(est.assumptions)
    return {
        **base,
        "assessment_id": ra.id, "has_zone": True, "confidence": ra.confidence, "method": ra.method,
        "observation": d["observation"], "pattern": d["pattern"], "pattern_label": d["pattern_label"],
        "onset_das": d["onset_das"], "onset_date": d["onset_date"], "ndvi_drop": d["ndvi_drop"],
        "recurrence_share": d["recurrence_share"], "weather": d["weather"], "urgency": d["urgency"],
        "urgency_reason": d["urgency_reason"], "worsening": d["worsening"], "priority_score": d["priority_score"],
        "priority_formula": d["priority_formula"], "next_step": d["next_step"], "prior_verified": d["prior_verified"],
        "disclaimer": "Hypotheses derived from a vegetation index and context. Not a diagnosis: confirm with an "
                      "inspection. Without an inspection, the maximum confidence is moderate.",
        "hypotheses": [dict(rank=h.rank, cause=h.cause, confidence=h.confidence, evidence=h.supporting_evidence,
                            missing=h.missing_data) for h in ra.hypotheses],
        "economics": dict(
            affected_ha=est.affected_ha, exposure_min=est.exposure_min, exposure_max=est.exposure_max,
            inspection_cost=est.inspection_cost, intervention_cost=est.intervention_cost,
            gross_value_brl=a.pop("gross_value_brl"), formula=a.pop("formula"), assumptions=a,
            label="Estimated exposure (not a confirmed loss)",
        ),
    }


def priorities(s: Session, farm_id: int, on: date) -> dict:
    fields = s.scalars(select(Field).where(Field.farm_id == farm_id).order_by(Field.code)).all()
    if not fields:
        raise NotFound("Farm has no fields")
    items = [assess_field(s, f.id, on) for f in fields]
    items.sort(key=lambda x: x["priority_score"], reverse=True)
    for i, it in enumerate(items, 1):
        it["rank"] = i
    zones = [i for i in items if i["has_zone"]]
    return dict(
        date=on, is_synthetic=True, priority_formula=eco.PRIORITY_FORMULA, items=items,
        totals=dict(
            exposure_min=round(sum(i["economics"]["exposure_min"] for i in zones), 2),
            exposure_max=round(sum(i["economics"]["exposure_max"] for i in zones), 2),
            affected_ha=round(sum(i["economics"]["affected_ha"] for i in zones), 1),
            inspection_cost=round(sum(i["economics"]["inspection_cost"] for i in zones), 2),
        ),
    )


# ------------------------------------------------------------------ field: history and memory
def field_detail(s: Session, field_id: int, on: date | None) -> dict:
    field = s.get(Field, field_id)
    if not field:
        raise NotFound("Field not found")
    season = s.scalars(select(CropSeason).where(CropSeason.farm_id == field.farm_id, CropSeason.is_current.is_(True))).one()
    on = on or field.farm.reference_date
    snaps = _season_snapshots(s, field.farm_id, season.id)  # includes simulated post-intervention observations
    evolution = []
    for sn in snaps:
        f = next(x for x in sn["fields"] if x["field_id"] == field_id)
        evolution.append(dict(date=sn["date"], das=sn["das"], cloud_pct=f["cloud_pct"], simulated=sn["simulated"],
                              red=f["area_by_level"]["red"], yellow=f["area_by_level"]["yellow"],
                              no_data=f["area_by_level"]["no_data"], ndvi=f["ndvi_mean"], baseline=f["ndvi_baseline"]))
    rain = s.execute(select(WeatherDaily.date, WeatherDaily.rain_mm, WeatherDaily.tmax_c).where(
        WeatherDaily.farm_id == field.farm_id, WeatherDaily.date >= season.sowing_date, WeatherDaily.date <= on,
    ).order_by(WeatherDaily.date)).all()
    return dict(
        field_id=field.id, code=field.code, name=field.name, area_ha=field.area_ha, soil_texture=field.soil_texture,
        irrigation=field.irrigation, boundary_source=field.boundary_source, is_synthetic=True,
        season=dict(id=season.id, name=season.name, sowing_date=season.sowing_date,
                    expected_yield_bags_ha=season.expected_yield_bags_ha),
        date=on, assessment=assess_field(s, field_id, on), evolution=evolution,
        weather=[dict(date=r.date, rain_mm=r.rain_mm, tmax_c=r.tmax_c) for r in rain],
        memory=memory(s, field_id),
        harvests=[dict(season=c.name, expected=c.expected_yield_bags_ha, realized=c.realized_yield_bags_ha)
                  for c in field.farm.seasons if c.realized_yield_bags_ha is not None],
    )


def memory(s: Session, field_id: int, q: str | None = None) -> list[dict]:
    stmt = select(MemoryEvent, CropSeason.name).outerjoin(CropSeason, CropSeason.id == MemoryEvent.season_id).where(
        MemoryEvent.field_id == field_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(MemoryEvent.title.ilike(like) | MemoryEvent.summary.ilike(like))
    rows = s.execute(stmt.order_by(MemoryEvent.date.desc(), MemoryEvent.id.desc())).all()
    return [dict(id=m.id, date=m.date, type=m.type, title=m.title, summary=m.summary, season=season,
                 refs=m.refs, is_synthetic=m.is_synthetic) for m, season in rows]


def weather(s: Session, farm_id: int, start: date, end: date) -> list[dict]:
    rows = s.scalars(select(WeatherDaily).where(
        WeatherDaily.farm_id == farm_id, WeatherDaily.date >= start, WeatherDaily.date <= end,
    ).order_by(WeatherDaily.date)).all()
    return [dict(date=w.date, rain_mm=w.rain_mm, tmax_c=w.tmax_c, tmin_c=w.tmin_c, is_synthetic=w.is_synthetic)
            for w in rows]


def warm_cache(farm_id: int | None = None) -> None:
    """Precompute snapshots and assessments for the reference date (called at startup)."""
    from app.infrastructure.db.models import Farm
    with SessionLocal() as s:
        farm = s.get(Farm, farm_id) if farm_id else s.scalars(select(Farm)).first()
        if not farm:
            return
        priorities(s, farm.id, farm.reference_date)
