"""Idempotent demo seed. Usage: python -m app.infrastructure.seed.seed [--reset]"""
import io
import sys
import time
from datetime import timedelta

import numpy as np
from shapely import MultiPolygon, unary_union
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.fmt import num
from app.infrastructure.db.base import SessionLocal, engine
from app.infrastructure.db.models import (
    AppSetting, CropSeason, Farm, Field, Inspection, Intervention, ManagementCell, MemoryEvent,
    OutcomeMeasurement, Task,
)
from app.infrastructure.seed import scenario as sc

FARM_NAME = "Santa Aurora Farm"
SEED_VERSION = 5  # bump when the scenario changes: the seed rebuilds the demo automatically
SETTINGS_SCHEMA = 5  # v5: English keys (older Portuguese keys are dropped and recreated)

DEFAULT_SETTINGS = {
    "economics": {
        "expected_yield_bags_ha": 62.0,
        "bag_price_brl": 120.0,
        "loss_min_pct": 8.0,
        "loss_max_pct": 25.0,
        "inspection_cost_brl": 450.0,
        "intervention_cost_brl_ha": 85.0,
    },
    "risk": {"yellow_threshold": 1.5, "red_threshold": 2.5, "history_weight": 0.6},
    "llm_provider": "auto",  # auto = use whichever key is available (Anthropic/OpenAI) or the DemoProvider
}


def _wkt(g, nd=7) -> str:
    from shapely import set_precision
    return set_precision(g, 10 ** -nd).wkt


def seed(reset: bool = False) -> None:
    t0 = time.time()
    with SessionLocal() as s:
        existing = s.scalar(select(Farm).order_by(Farm.id))
        ver = s.get(AppSetting, "seed_version")
        version = (ver.value.get("value", ver.value.get("valor")) if ver else None)
        if version is None or version < SETTINGS_SCHEMA:
            s.execute(delete(AppSetting))  # settings from the Portuguese version → recreate with English keys
            s.commit()
        if existing and version != SEED_VERSION:
            print(f"Demo scenario changed (version {SEED_VERSION}). Rebuilding…")
            reset = True
        if existing and not reset:
            print(f"Seed already applied (farm id={existing.id}). Use --reset to rebuild.")
            return
        if existing:
            s.execute(delete(Farm))  # cascades in the database
            s.commit()
        _seed(s)
    print(f"Seed finished in {time.time() - t0:.1f}s")


def _seed(s: Session) -> None:
    specs = sc.fields_spec()
    grid = sc.build_grid(specs, get_settings().cell_size_m)
    obs_sets, meta = sc.generate_observations(grid)

    fields_wgs = [sc.to_wgs(f["geom"]) for f in specs]
    farm_boundary = MultiPolygon([p for p in [unary_union(fields_wgs).convex_hull]])
    total_ha = float(grid.area_ha.sum())
    current = next(x for x in sc.SEASONS if x.is_current)
    ref_date = sc.das_dates(current)[-1][1]

    farm = Farm(
        name=FARM_NAME, municipality="Sorriso", state="MT", crop="Soybean", area_ha=round(total_ha, 1),
        reference_date=ref_date, is_synthetic=True,
        soil_notes="Mostly clayey Red-Yellow Oxisol; the southwest sector of F04 has a medium-to-sandy texture "
                   "and lower water-holding capacity. (Demo data)",
        boundary=f"SRID=4326;{_wkt(farm_boundary)}",
    )
    s.add(farm)
    s.flush()

    seasons = []
    for spec in sc.SEASONS:
        cs = CropSeason(
            farm_id=farm.id, name=spec.name, crop="Soybean", sowing_date=spec.sowing, harvest_date=spec.harvest,
            expected_yield_bags_ha=spec.expected_yield, realized_yield_bags_ha=spec.realized_yield,
            is_current=spec.is_current,
        )
        s.add(cs)
        seasons.append(cs)

    fields = []
    for i, (spec, g) in enumerate(zip(specs, fields_wgs)):
        f = Field(
            farm_id=farm.id, code=spec["code"], name=f"Field {spec['code'][1:]}",
            area_ha=round(float(grid.area_ha[grid.field_idx == i].sum()), 1),
            soil_texture=spec["soil"], irrigation=spec["irrigation"], boundary_source="synthetic_demo",
            geom=f"SRID=4326;{_wkt(g)}",
        )
        s.add(f)
        fields.append(f)
    s.flush()

    # cells
    cell_rows = [
        dict(field_id=fields[fi].id, row=int(r), col=int(c), area_ha=round(float(a), 4),
             geom=f"SRID=4326;{_wkt(sc.to_wgs(g))}")
        for fi, r, c, a, g in zip(grid.field_idx, grid.row, grid.col, grid.area_ha, grid.geoms)
    ]
    s.execute(ManagementCell.__table__.insert(), cell_rows)
    s.flush()
    cell_ids = np.array(s.scalars(
        select(ManagementCell.id).join(Field).where(Field.farm_id == farm.id)
        .order_by(ManagementCell.id)
    ).all())
    assert cell_ids.size == grid.cx.size

    # observations via COPY
    buf = io.StringIO()
    for o in obs_sets:
        sid = seasons[o.season_idx].id
        for cid, v, n, cl in zip(cell_ids, o.ndvi, o.ndre, o.cloud):
            buf.write(f"{cid}\t{sid}\t{o.date.isoformat()}\t{o.das}\t{v:.4f}\t{n:.4f}\t{'t' if cl else 'f'}\tdemo\tt\n")
    buf.seek(0)
    raw = s.connection().connection
    with raw.cursor().copy(
        "COPY observations (cell_id, season_id, date, das, ndvi, ndre, cloud_flag, source, is_synthetic) FROM STDIN"
    ) as cp:
        while chunk := buf.read(1 << 20):
            cp.write(chunk)

    # weather
    s.execute(text(
        "INSERT INTO weather_daily (farm_id, date, rain_mm, tmax_c, tmin_c, is_synthetic) "
        "VALUES (:f, :d, :r, :tx, :tn, true)"
    ), [dict(f=farm.id, d=d, r=r, tx=tx, tn=tn) for d, r, tx, tn in sc.generate_weather()])

    _seed_history(s, farm, fields, seasons, grid, obs_sets, meta)

    s.merge(AppSetting(key="seed_version", value={"value": SEED_VERSION}))
    for k, v in DEFAULT_SETTINGS.items():
        if not s.get(AppSetting, k):  # keep settings the user has edited
            s.add(AppSetting(key=k, value=v if isinstance(v, dict) else {"value": v}))
    s.commit()
    s.execute(text("ANALYZE observations"))
    s.commit()


def _seed_history(s, farm, fields, seasons, grid, obs_sets, meta) -> None:
    """Full 2024/25 cycle on F04 + memory events for the other fields."""
    f04 = fields[3]
    prev = seasons[1]
    a = sc.PREV_ANOMALY
    sector = meta["sector"]
    in_sector = sector > 0.5
    comparison = (grid.field_idx == 3) & (sector < 0.05)

    def window_mean(mask, das_from, das_to):
        vals = [o.ndvi[mask & ~o.cloud].mean() for o in obs_sets
                if o.season_idx == 1 and das_from <= o.das <= das_to and (mask & ~o.cloud).any()]
        return float(np.mean(vals))

    d = lambda das: prev.sowing_date + timedelta(days=das)
    affected_ha = round(float(grid.area_ha[in_sector].sum()), 1)
    sector_geom = sc.to_wgs(unary_union([g for g, m in zip(grid.geoms, in_sector) if m]).buffer(0.5).buffer(-0.5))
    if sector_geom.geom_type == "Polygon":
        sector_geom = MultiPolygon([sector_geom])
    sector_wkt = f"SRID=4326;{_wkt(sector_geom)}"

    task = Task(
        farm_id=farm.id, field_id=f04.id, title="Inspection — southwest sector of the pivot (F04)", kind="inspection",
        priority="high", assignee="Carlos Menezes (field technician)", due_date=d(a["peak"] + 1),
        instructions="Walk the southwest sector of the pivot. Check for water-stress symptoms (midday wilting), "
                     "run beat-sheet sampling for stink bugs and caterpillars, and check the sprinklers on the last "
                     "towers.",
        status="verified", geom=sector_wkt,
    )
    s.add(task)
    s.flush()
    insp = Inspection(
        task_id=task.id, inspected_at=d(a["peak"] + 2), recorded_by="Carlos Menezes",
        verified_cause="Water stress",
        findings="Plants wilting at midday and leaflets flipped in the southwest sector. Clogged sprinklers on the "
                 "last two towers of the pivot. Beat-sheet counts below the stink-bug action threshold.",
        notes="Sandier soil in this sector. Recommended reviewing sprinklers and applied irrigation depth.",
        photos=[],
    )
    s.add(insp)
    s.flush()
    interv = Intervention(
        field_id=f04.id, inspection_id=insp.id,
        recommended_action="Review the sprinklers on the last towers and adjust irrigation depth in the affected sector.",
        approved_action="Cleaned/replaced sprinklers on towers 7 and 8 and raised irrigation depth to 8 mm/day in "
                        "the southwest sector for 10 days.",
        approved_by="Mariana Rocha, agronomist (CREA-MT)", executed_at=d(a["intervention_das"]),
        actual_cost=round(affected_ha * 92.0, 2),
        notes="Costs include labor, parts and estimated extra energy. (Demo data)",
    )
    s.add(interv)
    s.flush()

    bf, bt = a["peak"] - 5, a["intervention_das"] - 1
    af, at = a["intervention_das"] + 9, a["intervention_das"] + 19
    b, af_v = window_mean(in_sector, bf, bt), window_mean(in_sector, af, at)
    cb, ca = window_mean(comparison, bf, bt), window_mean(comparison, af, at)
    outcome = OutcomeMeasurement(
        intervention_id=interv.id, metric="ndvi",
        before_start=d(bf), before_end=d(bt), after_start=d(af), after_end=d(at),
        before_value=round(b, 3), after_value=round(af_v, 3),
        comparison_before=round(cb, 3), comparison_after=round(ca, 3),
        delta=round(af_v - b, 3), delta_vs_comparison=round((af_v - b) - (ca - cb), 3),
        method="Simple difference-in-differences: change in the mean NDVI of the affected sector between the "
               "before and after windows, net of the change in the rest of the pivot (comparison area) over the "
               "same period. Cloudy observations discarded.",
        comparison_area="Rest of F04 (same pivot, cultivar and sowing date), outside the southwest sector.",
        limitations="Rain returned during the same period, which also contributes to the recovery. Single event; "
                    "no untreated control plot. Indicates association, not proof of causation.",
        confidence="moderate",
    )
    s.add(outcome)

    ev = lambda f, season, date_, typ, title, summary, refs=None: MemoryEvent(
        field_id=f.id, season_id=season.id, date=date_, type=typ, title=title, summary=summary, refs=refs or {},
    )
    sign = "+" if outcome.delta_vs_comparison >= 0 else "−"
    s.add_all([
        ev(f04, prev, prev.sowing_date, "season", "2024/25 season sowing", "Soybean sown under the center pivot."),
        ev(f04, prev, d(a["onset"] + 8), "anomaly", "NDVI drop in the southwest sector of the pivot",
           f"NDVI below the area's own history and the field median across ~{num(affected_ha, 0)} ha, "
           "after 12 days without rain.", {"area_ha": affected_ha}),
        ev(f04, prev, insp.inspected_at, "inspection", "Inspection confirmed water stress",
           insp.findings, {"task_id": task.id, "inspection_id": insp.id}),
        ev(f04, prev, interv.executed_at, "intervention", "Pivot sprinkler and irrigation-depth fix",
           f"{interv.approved_action} Actual cost: R$ {num(interv.actual_cost, 2)}.",
           {"intervention_id": interv.id}),
        ev(f04, prev, d(at), "outcome", "Sector NDVI partially recovered",
           f"Sector NDVI: {num(b, 2)} → {num(af_v, 2)}; comparison area: {num(cb, 2)} → {num(ca, 2)}. "
           f"Net difference {sign}{num(abs(outcome.delta_vs_comparison), 2)}. Rain also returned in the period — "
           "association, not proof of causation.", {"intervention_id": interv.id}),
        ev(f04, prev, prev.harvest_date, "season", "2024/25 season harvest",
           f"Field average yield: {num(prev.realized_yield_bags_ha, 1)} bags/ha "
           f"(expected {num(prev.expected_yield_bags_ha, 0)})."),
    ])
    for f in fields:
        for season in seasons:
            if f is f04 and season is prev:
                continue
            s.add(ev(f, season, season.sowing_date, "season", f"{season.name} season sowing",
                     f"Soybean sown in {f.name}."))
    s.add(ev(fields[2], seasons[2], seasons[2].sowing_date + timedelta(days=21), "note",
             "Uneven stand observed at emergence",
             "Operator reported planting skips in a diagonal strip across the field (possible planter problem)."))

if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
