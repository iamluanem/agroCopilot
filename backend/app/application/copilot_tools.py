"""Copilot tools. They read real app data; none of them writes without the user's confirmation."""
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.application import intelligence as intel
from app.application.map_service import NotFound, risk_snapshot
from app.domain import economics as eco
from app.infrastructure.db.models import (
    Farm, Field, Inspection, Intervention, OutcomeMeasurement, Task,
)


@dataclass
class ToolContext:
    s: Session
    farm: Farm

    @property
    def ref(self) -> date:
        return self.farm.reference_date


def _iso(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _iso(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_iso(x) for x in v]
    return v


def resolve_field(ctx: ToolContext, ref: str | int | None) -> Field:
    if ref is None or ref == "":
        raise NotFound("Specify the field (e.g. F04)")
    fields = ctx.farm.fields
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit() and int(ref) > 20):
        f = next((x for x in fields if x.id == int(ref)), None)
        if f:
            return f
    m = re.search(r"(\d{1,2})", str(ref))
    if m:
        code = f"F{int(m.group(1)):02d}"
        f = next((x for x in fields if x.code == code), None)
        if f:
            return f
    raise NotFound(f"Field '{ref}' not found. Available: {', '.join(x.code for x in fields)}")


def _trim_assessment(a: dict) -> dict:
    keep = ("field_id", "code", "name", "area_ha", "date", "das", "stage", "level", "red_ha", "yellow_ha",
            "ndvi_mean", "ndvi_baseline", "assessment_id", "has_zone", "summary", "confidence", "observation",
            "pattern_label", "onset_das", "onset_date", "ndvi_drop", "recurrence_share", "weather", "urgency",
            "urgency_reason", "worsening", "priority_score", "next_step", "prior_verified", "hypotheses", "economics",
            "rank")
    return {k: a[k] for k in keep if k in a}


# ------------------------------------------------------------------ tools
def get_farm_summary(ctx: ToolContext) -> dict:
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    pr = intel.priorities(ctx.s, ctx.farm.id, ctx.ref)
    return dict(
        farm=ctx.farm.name, location=f"{ctx.farm.municipality}-{ctx.farm.state}, Brazil", crop=ctx.farm.crop,
        reference_date=ctx.ref, das=snap["das"], stage=eco.soybean_stage(snap["das"]), season=snap["season_name"],
        total_area_ha=snap["summary"]["total_ha"], pct_by_level=snap["summary"]["pct_by_level"],
        area_by_level_ha=snap["summary"]["area_by_level"], total_exposure=pr["totals"],
        priorities=[dict(rank=i["rank"], field=i["code"], name=i["name"], level=i["level"], critical_area_ha=i["red_ha"],
                         watch_area_ha=i["yellow_ha"],
                         top_hypothesis=(i["hypotheses"][0]["cause"] if i["hypotheses"] else None),
                         hypothesis_confidence=(i["hypotheses"][0]["confidence"] if i["hypotheses"] else None),
                         exposure_min=(i["economics"] or {}).get("exposure_min"),
                         exposure_max=(i["economics"] or {}).get("exposure_max"),
                         assessment_id=i["assessment_id"], next_step=i.get("next_step")) for i in pr["items"]],
        priority_formula=pr["priority_formula"], synthetic_data=True,
    )


def get_field_risk(ctx: ToolContext, field: str, date_: str | None = None) -> dict:
    f = resolve_field(ctx, field)
    on = date.fromisoformat(date_) if date_ else ctx.ref
    return _trim_assessment(intel.assess_field(ctx.s, f.id, on))


def get_cell_history(ctx: ToolContext, cell_id: int) -> dict:
    rows = ctx.s.execute(text("""
        SELECT cs.name season, o.date, o.das, o.ndvi, o.cloud_flag, c.field_id
        FROM observations o JOIN crop_seasons cs ON cs.id=o.season_id JOIN management_cells c ON c.id=o.cell_id
        WHERE o.cell_id=:c ORDER BY o.date
    """), {"c": cell_id}).all()
    if not rows:
        raise NotFound(f"Cell {cell_id} not found")
    f = ctx.s.get(Field, rows[0].field_id)
    by_season: dict[str, list] = {}
    for r in rows:
        by_season.setdefault(r.season, []).append(dict(das=r.das, ndvi=None if r.cloud_flag else round(r.ndvi, 3)))
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    i = snap["cells"]["id"].index(cell_id)
    return dict(cell_id=cell_id, field=f.code, current_level=snap["levels"][snap["cells"]["level"][i]],
                score=snap["cells"]["score"][i], current_ndvi=snap["cells"]["ndvi"][i],
                history_same_das=snap["cells"]["baseline"][i], series=by_season, synthetic_data=True)


def compare_fields(ctx: ToolContext, fields: list[str] | None = None) -> dict:
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    wanted = {resolve_field(ctx, x).id for x in fields} if fields else None
    return dict(date=ctx.ref, fields=[
        dict(field=f["code"], level=f["level"], ndvi_mean=f["ndvi_mean"], ndvi_history=f["ndvi_baseline"],
             critical_area_ha=f["area_by_level"]["red"], watch_area_ha=f["area_by_level"]["yellow"],
             cloud_pct=f["cloud_pct"])
        for f in snap["fields"] if wanted is None or f["field_id"] in wanted
    ])


def get_weather(ctx: ToolContext, days: int = 30) -> dict:
    days = max(7, min(int(days), 120))
    rows = intel.weather(ctx.s, ctx.farm.id, ctx.ref - timedelta(days=days - 1), ctx.ref)
    season = next(x for x in ctx.farm.seasons if x.is_current)
    w = intel._weather_context(ctx.s, ctx.farm.id, ctx.ref, season.sowing_date)
    return dict(period_days=days, total_rain_mm=round(sum(r["rain_mm"] for r in rows), 1),
                longest_dry_run_days=w["max_dry_days"], dry_start=w["dry_start"], dry_end=w["dry_end"],
                mean_tmax_dry_period=w["tmax_dry_mean"] and round(w["tmax_dry_mean"], 1),
                rain_last_21d_mm=w["rain_21d_mm"], synthetic_data=True,
                daily=[dict(date=r["date"], rain_mm=r["rain_mm"], tmax=r["tmax_c"]) for r in rows[-14:]])


def get_memory(ctx: ToolContext, field: str, query: str | None = None) -> dict:
    f = resolve_field(ctx, field)
    events = intel.memory(ctx.s, f.id, query) if query else intel.memory(ctx.s, f.id)
    if query and not events:  # empty search: return the whole memory and let the model decide
        events = intel.memory(ctx.s, f.id)
    return dict(field=f.code, events=[e for e in events if e["type"] != "season" or not query][:30],
                synthetic_data=True)


def list_tasks(ctx: ToolContext, field: str | None = None, status: str | None = None) -> dict:
    q = select(Task).where(Task.farm_id == ctx.farm.id).order_by(Task.created_at.desc())
    if field:
        q = q.where(Task.field_id == resolve_field(ctx, field).id)
    if status:
        q = q.where(Task.status == status)
    out = []
    for t in ctx.s.scalars(q):
        insp = ctx.s.scalars(select(Inspection).where(Inspection.task_id == t.id)).first()
        f = ctx.s.get(Field, t.field_id)
        out.append(dict(id=t.id, field=f.code, title=t.title, status=t.status, priority=t.priority,
                        assignee=t.assignee, due_date=t.due_date,
                        inspection=dict(date=insp.inspected_at, verified_cause=insp.verified_cause,
                                        findings=insp.findings) if insp else None))
    return dict(tasks=out, open=sum(1 for t in out if t["status"] not in ("completed", "verified")))


def estimate_economics(ctx: ToolContext, field: str, bag_price_brl: float | None = None,
                       expected_yield_bags_ha: float | None = None) -> dict:
    a = get_field_risk(ctx, field)
    if not a["has_zone"]:
        return dict(field=a["code"], message=a["summary"])
    base = intel.get_assumptions(ctx.s)
    over = {k: v for k, v in dict(bag_price_brl=bag_price_brl,
                                  expected_yield_bags_ha=expected_yield_bags_ha).items() if v}
    if not over:  # no simulation: return exactly the persisted assessment record
        x = a["economics"]
        return dict(field=a["code"], assessment_id=a["assessment_id"], simulation=False,
                    affected_area_ha=x["affected_ha"], exposure_min=x["exposure_min"], exposure_max=x["exposure_max"],
                    inspection_cost=x["inspection_cost"], estimated_intervention_cost=x["intervention_cost"],
                    gross_area_value=x["gross_value_brl"], formula=x["formula"], assumptions=x["assumptions"],
                    label=x["label"])
    p = a["economics"]["assumptions"]
    assumptions = eco.EconomicAssumptions(**{**base.__dict__, **over})
    e = eco.estimate_exposure(p["critical_area_ha"], p["watch_area_ha"], assumptions)
    return dict(field=a["code"], assessment_id=a["assessment_id"], simulation=True,
                affected_area_ha=e.affected_ha, exposure_min=e.exposure_min, exposure_max=e.exposure_max,
                inspection_cost=e.inspection_cost, estimated_intervention_cost=e.intervention_cost,
                gross_area_value=e.gross_value_brl, formula=e.formula, assumptions=e.assumptions,
                label="Estimated exposure — not a confirmed loss or realized savings")


def get_intervention_outcomes(ctx: ToolContext, field: str) -> dict:
    f = resolve_field(ctx, field)
    rows = ctx.s.execute(select(Intervention, OutcomeMeasurement).outerjoin(
        OutcomeMeasurement, OutcomeMeasurement.intervention_id == Intervention.id,
    ).where(Intervention.field_id == f.id).order_by(Intervention.executed_at.desc())).all()
    seasons = sorted(ctx.farm.seasons, key=lambda x: x.sowing_date)
    season_of = lambda d: next((x.name for x in reversed(seasons) if x.sowing_date <= d), None)
    current = next(x.name for x in seasons if x.is_current)
    return dict(field=f.code, current_season=current, interventions=[dict(
        id=i.id, season=season_of(i.executed_at), executed_at=i.executed_at, approved_action=i.approved_action,
        approved_by=i.approved_by, simulated_post_observations=bool(o and not i.is_synthetic),
        actual_cost=i.actual_cost,
        outcome=dict(metric=o.metric, before=o.before_value, after=o.after_value,
                     comparison_before=o.comparison_before, comparison_after=o.comparison_after,
                     delta=o.delta, net_delta_vs_comparison=o.delta_vs_comparison, method=o.method,
                     comparison_area=o.comparison_area, limitations=o.limitations, confidence=o.confidence,
                     before_window=[o.before_start, o.before_end], after_window=[o.after_start, o.after_end])
        if o else None) for i, o in rows], synthetic_data=True)


def propose_inspection(ctx: ToolContext, field: str) -> dict:
    a = get_field_risk(ctx, field)
    if not a["has_zone"]:
        return dict(field=a["code"], message="No anomaly zone that justifies an inspection right now.")
    top = a["hypotheses"][0]
    checklist = "; ".join(m for h in a["hypotheses"][:2] for m in h["missing"])
    return dict(proposed_task=dict(
        field_id=a["field_id"], field_code=a["code"], assessment_id=a["assessment_id"],
        title=f"Inspection — anomaly zone in {a['name']} ({a['red_ha']:.0f} critical ha)",
        priority="high" if a["red_ha"] >= 10 else "medium", assignee="Carlos Menezes (field technician)",
        due_date=(ctx.ref + timedelta(days=2)).isoformat(),
        instructions=f"Top hypothesis: {top['cause']} ({top['confidence']} confidence). Check: {checklist}. "
                     "Record geotagged photos and the verified cause.",
    ), note="Proposal not saved. Requires the user's confirmation.")


# ------------------------------------------------------------------ registry
FIELD_ARG = {"type": "string", "description": "Field code, e.g. F04"}
TOOLS: dict[str, tuple[Callable, str, dict]] = {
    "get_farm_summary": (get_farm_summary, "Farm summary on the reference date: % by risk level, total exposure and "
                         "fields ranked by priority.", {"type": "object", "properties": {}}),
    "get_field_risk": (get_field_risk, "Assessment of one field: anomaly zone, observation, hypotheses with evidence and "
                       "missing data, R$ exposure, urgency and next step.",
                       {"type": "object", "properties": {"field": FIELD_ARG, "date_": {"type": "string",
                        "description": "Date YYYY-MM-DD (optional; default = reference date)"}}, "required": ["field"]}),
    "get_cell_history": (get_cell_history, "NDVI series of one management cell by season and its current risk.",
                         {"type": "object", "properties": {"cell_id": {"type": "integer"}}, "required": ["cell_id"]}),
    "compare_fields": (compare_fields, "Compare current NDVI, history and anomaly areas across fields.",
                       {"type": "object", "properties": {"fields": {"type": "array", "items": FIELD_ARG}}}),
    "get_weather": (get_weather, "Recent rain and temperature (synthetic) and the longest run without rain.",
                    {"type": "object", "properties": {"days": {"type": "integer", "minimum": 7, "maximum": 120}}}),
    "get_memory": (get_memory, "Field agronomic memory: past anomalies, inspections, interventions and outcomes.",
                   {"type": "object", "properties": {"field": FIELD_ARG, "query": {"type": "string"}}, "required": ["field"]}),
    "list_tasks": (list_tasks, "List operational tasks (inspections) with status and findings.",
                   {"type": "object", "properties": {"field": FIELD_ARG, "status": {"type": "string"}}}),
    "estimate_economics": (estimate_economics, "Estimated economic exposure for a field, with assumptions; can simulate "
                           "the bag price or expected yield.",
                           {"type": "object", "properties": {"field": FIELD_ARG, "bag_price_brl": {"type": "number"},
                            "expected_yield_bags_ha": {"type": "number"}}, "required": ["field"]}),
    "get_intervention_outcomes": (get_intervention_outcomes, "Interventions recorded in the field and the measured "
                                  "outcome (before/after, comparison area, method, limitations).",
                                  {"type": "object", "properties": {"field": FIELD_ARG}, "required": ["field"]}),
    "propose_inspection": (propose_inspection, "Draft an inspection proposal for the anomaly zone. Does NOT save it: "
                           "the user confirms on screen.",
                           {"type": "object", "properties": {"field": FIELD_ARG}, "required": ["field"]}),
}


def run_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}
    fn = TOOLS[name][0]
    try:
        return _iso(fn(ctx, **(args or {})))
    except NotFound as e:
        return {"error": str(e)}
    except TypeError as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
