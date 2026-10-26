"""DemoProvider: deterministic, rule-based copilot.

Uses the SAME tools as the LLM providers and builds the structured answer from the data they return.
Runs without an API key — ideal for recording the demo at no cost and with no variation.
"""
import re
from datetime import date

from app.application.copilot_tools import ToolContext, run_tool
from app.core.fmt import num
from app.domain.copilot import CopilotAnswer, CopilotRequest, ProposedTask, Source, ToolCall

DEMO_ALERT = "Demo data (synthetic): not real satellite measurements or real field operations."
CAUSAL = "Improvement after an intervention indicates association, not proof of causation."
FIELD_RE = r"\b(?:f|field)\s*0?(\d{1,2})\b"


def _brl(v: float | None) -> str:
    return "—" if v is None else f"R$ {num(v, 0)}"


def _d(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%b %-d, %Y") if iso else "—"


class DemoProvider:
    name = "demo"
    label = "DemoProvider (rules, no LLM)"

    def answer(self, req: CopilotRequest, ctx: ToolContext) -> tuple[CopilotAnswer, list[ToolCall]]:
        self.calls: list[ToolCall] = []
        self.ctx = ctx
        q = req.question.lower()
        field = self._field_from(q, req)

        if re.search(r"\b(create|schedule|open|add|book|plan|make)\b.*\b(inspection|task|visit|scouting)", q):
            return self._propose(field), self.calls
        if re.search(r"\b(tasks?|pending|open tasks?|inspections?)\b", q) and not re.search(r"(create|schedule)", q):
            explicit = re.search(FIELD_RE, q)
            return self._tasks(field if explicit else None), self.calls
        if re.search(r"(evolv|after the intervention|since the intervention|recover|outcome|did it work|result)", q):
            return self._outcomes(field), self.calls
        if re.search(r"(happen|history|what worked|last season|previous season|last year|memory|seen this|before\?)", q):
            return self._history(field), self.calls
        if re.search(r"(loss|r\$|how much|exposure|cost|money|value|financial|price|bag|yield)", q):
            return self._economics(field, q), self.calls
        if re.search(r"(rain|weather|dry|drought|temperature|heat)", q):
            return self._weather(), self.calls
        if re.search(r"compar", q):
            return self._compare(), self.calls
        if re.search(r"(why|explain|reason|cause|red\b|yellow|critical|what.?s (going on|happening))", q) and field:
            return self._why(field), self.calls
        known = re.search(r"(attention|priorit|today|which|summary|status|overview|urgent|focus)", q)
        return self._summary(fallback=not known), self.calls

    # ------------------------------------------------------------------ helpers
    def _tool(self, name: str, **args) -> dict:
        self.calls.append(ToolCall(name=name, args=args))
        return run_tool(self.ctx, name, args)

    def _field_from(self, q: str, req: CopilotRequest) -> str | None:
        m = re.search(FIELD_RE, q)
        if m:
            return f"F{int(m.group(1)):02d}"
        if req.field_id:
            f = next((x for x in self.ctx.farm.fields if x.id == req.field_id), None)
            if f:
                return f.code
        for h in reversed(req.history):
            m = re.search(FIELD_RE, str(h.get("content", "")).lower())
            if m:
                return f"F{int(m.group(1)):02d}"
        if re.search(r"(here|this field|this area|that field|that area)", q):
            return self._top_field()
        return None

    def _top_field(self) -> str | None:
        s = self._tool("get_farm_summary")
        top = next((p for p in s["priorities"] if p["exposure_min"]), None)
        return top["field"] if top else None

    # ------------------------------------------------------------------ intents
    def _summary(self, fallback: bool = False) -> CopilotAnswer:
        s = self._tool("get_farm_summary")
        zones = [p for p in s["priorities"] if p["exposure_min"]]
        pct = s["pct_by_level"]
        ev = [f"{num(pct['green'], 1)}% of the area is healthy, {num(pct['yellow'], 1)}% on watch and "
              f"{num(pct['red'], 1)}% critical on {_d(s['reference_date'])} (DAS {s['das']}, {s['stage']})."]
        for p in zones:
            ev.append(f"#{p['rank']} {p['field']}: {num(p['critical_area_ha'], 1)} critical ha and "
                      f"{num(p['watch_area_ha'], 1)} watch ha; top hypothesis {p['top_hypothesis'].lower()} "
                      f"({p['hypothesis_confidence']} confidence); estimated exposure "
                      f"{_brl(p['exposure_min'])}–{_brl(p['exposure_max'])}.")
        ok = [p["field"] for p in s["priorities"] if not p["exposure_min"]]
        if ok:
            ev.append(f"{', '.join(ok)}: no relevant anomaly zone.")
        if zones:
            top = zones[0]
            summary = (f"{len(zones)} field(s) need attention. Start with {top['field']}: the highest estimated "
                       f"exposure ({_brl(top['exposure_min'])}–{_brl(top['exposure_max'])}) at a sensitive crop stage.")
            nxt = f"Schedule an inspection of {top['field']} before deciding on any intervention. I can draft the task."
        else:
            summary, nxt = "No field has a relevant anomaly zone on this date.", "Keep monitoring the next scenes."
        if fallback:
            summary = "I can't answer that from the app's data yet. Here is the current farm status. " + summary
        return CopilotAnswer(
            summary=summary, evidence=ev, confidence="moderate",
            missing_data=["Field inspections of the anomaly zones"], next_action=nxt,
            sources=[Source(type="assessment", label=f"{p['field']} assessment on {_d(s['reference_date'])}",
                            ref=f"risk_assessment:{p['assessment_id']}") for p in zones]
            + [Source(type="observations", label=f"Risk snapshot on {_d(s['reference_date'])}")],
            warnings=[DEMO_ALERT, "Priority = exposure × urgency × confidence; exposure is not a confirmed loss."],
        )

    def _why(self, field: str) -> CopilotAnswer:
        a = self._tool("get_field_risk", field=field)
        if "error" in a:
            return self._error(a["error"])
        if not a["has_zone"]:
            return CopilotAnswer(summary=f"{a['code']} has no relevant anomaly zone on {_d(a['date'])}. {a['summary']}",
                                 evidence=[f"Mean NDVI {num(a['ndvi_mean'], 2)} vs. history {num(a['ndvi_baseline'], 2)}."],
                                 confidence="moderate", next_action="Keep monitoring.",
                                 sources=[Source(type="observations", label=f"Snapshot on {_d(a['date'])}")],
                                 warnings=[DEMO_ALERT])
        h = a["hypotheses"]
        top = h[0]
        level = {"red": "critical", "yellow": "on watch"}.get(a["level"], a["level"])
        others = ", ".join(f"{x['cause'].lower()} ({x['confidence']})" for x in h[1:3])
        return CopilotAnswer(
            summary=(f"{a['code']} is {level} because its NDVI dropped below the area's own history. The most likely "
                     f"hypothesis is {top['cause'].lower()} ({top['confidence']} confidence), but this is not a diagnosis "
                     f"yet: it needs a field inspection. Less likely alternatives: {others}."),
            evidence=[a["observation"]] + top["evidence"], confidence=top["confidence"], missing_data=top["missing"],
            next_action=a["next_step"],
            sources=[Source(type="assessment", label=f"{a['code']} assessment on {_d(a['date'])}",
                            ref=f"risk_assessment:{a['assessment_id']}"),
                     Source(type="weather", label="Daily weather, last 30 days")]
            + [Source(type="memory", label=f"{p['season']} inspection: {p['cause']}") for p in a["prior_verified"]],
            warnings=[DEMO_ALERT, "A satellite index directs the inspection; it does not confirm the cause."],
        )

    def _economics(self, field: str | None, q: str) -> CopilotAnswer:
        field = field or self._top_field()
        price = re.search(r"(?:bag|price)[^\d]{0,20}(\d{2,3}(?:\.\d+)?)", q) or re.search(r"r\$\s*(\d{2,3}(?:\.\d+)?)", q)
        args = {"field": field}
        if price:
            args["bag_price_brl"] = float(price.group(1))
        e = self._tool("estimate_economics", **args)
        if "error" in e or "message" in e:
            return self._error(e.get("error") or e["message"])
        p = e["assumptions"]
        sim = f" (simulation with the bag at {_brl(p['bag_price_brl'])})" if e["simulation"] else ""
        return CopilotAnswer(
            summary=(f"Estimated exposure for {e['field']}{sim}: {_brl(e['exposure_min'])} to {_brl(e['exposure_max'])}. "
                     "It is a risk range on the production of the affected area — not a confirmed loss."),
            evidence=[f"Affected area {num(e['affected_area_ha'], 1)} ha = {num(p['critical_area_ha'], 1)} critical ha + "
                      f"50% of {num(p['watch_area_ha'], 1)} watch ha.",
                      f"Gross value of the area: {num(e['affected_area_ha'], 1)} ha × "
                      f"{num(p['expected_yield_bags_ha'], 0)} bags/ha × {_brl(p['bag_price_brl'])}/bag = "
                      f"{_brl(e['gross_area_value'])}.",
                      f"Loss range considered: {num(p['loss_min_pct'], 0)}% to {num(p['loss_max_pct'], 0)}%.",
                      f"Inspection cost {_brl(e['inspection_cost'])}; estimated intervention "
                      f"{_brl(e['estimated_intervention_cost'])}."],
            confidence="low" if e["simulation"] else "moderate",
            missing_data=["Cause confirmed by inspection (determines whether the loss is reversible)",
                          "Realized yield at harvest to calibrate the loss range"],
            next_action=(f"Inspect the zone: a {_brl(e['inspection_cost'])} inspection against an exposure of up to "
                         f"{_brl(e['exposure_max'])}."),
            sources=[Source(type="economics", label=f"Economic model — {e['field']}", ref=f"risk_assessment:{e['assessment_id']}"),
                     Source(type="settings", label="Economic assumptions (Settings)")],
            warnings=[DEMO_ALERT, "Estimate based on editable assumptions; not a realized loss or saving."],
        )

    def _history(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        m = self._tool("get_memory", field=field)
        o = self._tool("get_intervention_outcomes", field=field)
        if "error" in m:
            return self._error(m["error"])
        prev_only = lambda e: e.get("season") != o.get("current_season")
        relevant = [e for e in m["events"] if e["type"] in ("anomaly", "inspection", "intervention", "outcome", "note")
                    and prev_only(e)]
        done = [i for i in o["interventions"] if i["outcome"] and i["season"] != o.get("current_season")]
        if not relevant:
            return CopilotAnswer(summary=f"There is no record of a previous anomaly, inspection or intervention in {m['field']}.",
                                 confidence="high", next_action="Record the current inspection to start this field's memory.",
                                 missing_data=["Operational history from before the app was in use"],
                                 sources=[Source(type="memory", label=f"{m['field']} memory")], warnings=[DEMO_ALERT])
        ev = [f"{_d(e['date'])} — {e['title']}: {e['summary']}" for e in sorted(relevant, key=lambda e: e["date"])]
        if done:
            i = done[0]
            r = i["outcome"]
            action = i["approved_action"].split(" in the ")[0].rstrip(".").lower()
            summary = (f"Yes. In the {i['season']} season {m['field']} had a similar anomaly; the inspection confirmed the "
                       f"cause and the team {action} (cost {_brl(i['actual_cost'])}). Sector NDVI went from "
                       f"{num(r['before'], 2)} to {num(r['after'], 2)}, a net gain of {num(r['net_delta_vs_comparison'], 2)} "
                       "vs. the comparison area — a partial recovery, with caveats.")
            missing = ["Confirm by inspection whether the current cause is the same as last season's"]
            nxt = "Inspect, prioritizing what worked before (pivot sprinklers and irrigation depth), without assuming the same cause."
            ev.append(f"Limitations of the previous result: {r['limitations']}")
            conf = r["confidence"]
        else:
            summary = f"There are previous records in {m['field']}, but no measured intervention outcome."
            missing, nxt, conf = ["Outcome measurement of past interventions"], "Review the field memory.", "low"
        return CopilotAnswer(
            summary=summary, evidence=ev, confidence=conf, missing_data=missing, next_action=nxt,
            sources=[Source(type="memory", label=f"{e['title']} ({_d(e['date'])})", ref=f"memory_event:{e['id']}") for e in relevant]
            + [Source(type="outcome", label=f"Intervention #{i['id']} outcome", ref=f"intervention:{i['id']}") for i in done],
            warnings=[DEMO_ALERT, CAUSAL],
        )

    def _outcomes(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        o = self._tool("get_intervention_outcomes", field=field)
        if "error" in o:
            return self._error(o["error"])
        done = [i for i in o["interventions"] if i["outcome"]]
        if not done:
            return CopilotAnswer(summary=f"There is no intervention with a measured outcome in {o['field']}.", confidence="high",
                                 next_action="After an intervention, record it and simulate/measure the following scenes.",
                                 missing_data=["A recorded intervention and post-intervention observations"],
                                 sources=[Source(type="outcome", label=f"{o['field']} interventions")], warnings=[DEMO_ALERT])
        i = done[0]
        r = i["outcome"]
        sim = " (simulated post-intervention observations)" if i.get("simulated_post_observations") else ""
        return CopilotAnswer(
            summary=(f"After the intervention on {_d(i['executed_at'])} in {o['field']}{sim}, the sector NDVI went from "
                     f"{num(r['before'], 2)} to {num(r['after'], 2)}; net of the comparison area, a gain of "
                     f"{num(r['net_delta_vs_comparison'], 2)}."),
            evidence=[f"Method: {r['method']}", f"Comparison: {r['comparison_area']}",
                      f"Comparison area: {num(r['comparison_before'], 2)} → {num(r['comparison_after'], 2)}."],
            confidence=r["confidence"], missing_data=[r["limitations"]],
            next_action="Use this result as a reference, not a guarantee, for the current decision.",
            sources=[Source(type="outcome", label=f"Intervention #{i['id']} outcome", ref=f"intervention:{i['id']}")],
            warnings=[DEMO_ALERT, CAUSAL],
        )

    def _weather(self) -> CopilotAnswer:
        w = self._tool("get_weather", days=30)
        return CopilotAnswer(
            summary=(f"Over the last 30 days it rained {num(w['total_rain_mm'], 0)} mm, with {w['longest_dry_run_days']} "
                     f"consecutive days without rain ({_d(w['dry_start'])}–{_d(w['dry_end'])})."),
            evidence=[f"Mean max temperature in the dry spell: {num(w['mean_tmax_dry_period'] or 0, 1)} °C.",
                      f"Rain in the last 21 days: {num(w['rain_last_21d_mm'], 0)} mm."],
            confidence="high", missing_data=["Soil moisture measured in the field"],
            next_action="Cross-check the dry spell with the anomaly zones (ask: why is F04 red?).",
            sources=[Source(type="weather", label="Daily weather (synthetic)")], warnings=[DEMO_ALERT],
        )

    def _compare(self) -> CopilotAnswer:
        c = self._tool("compare_fields")
        rows = sorted(c["fields"], key=lambda x: (x["ndvi_mean"] or 0) - (x["ndvi_history"] or 0))
        ev = [f"{t['field']}: NDVI {num(t['ndvi_mean'], 2)} vs. history {num(t['ndvi_history'], 2)} "
              f"({num(t['critical_area_ha'], 1)} critical ha, {num(t['watch_area_ha'], 1)} watch ha)." for t in rows]
        return CopilotAnswer(summary=f"{rows[0]['field']} has the largest negative deviation from its own history.",
                             evidence=ev, confidence="high", next_action=f"Open {rows[0]['field']} for details.",
                             sources=[Source(type="observations", label=f"Snapshot on {_d(c['date'])}")], warnings=[DEMO_ALERT])

    def _tasks(self, field: str | None) -> CopilotAnswer:
        t = self._tool("list_tasks", **({"field": field} if field else {}))
        ev = [f"#{x['id']} {x['field']} — {x['title']} · {x['status']}" + (
            f" · verified cause: {x['inspection']['verified_cause']}" if x["inspection"] else "") for x in t["tasks"]]
        return CopilotAnswer(
            summary=f"{t['open']} open task(s) out of {len(t['tasks'])} recorded" + (f" in {field}." if field else " on the farm."),
            evidence=ev or ["No tasks recorded."], confidence="high",
            next_action="Create an inspection for the priority zone." if t["open"] == 0 else "Follow up on the open tasks.",
            sources=[Source(type="task", label=f"Task #{x['id']}", ref=f"task:{x['id']}") for x in t["tasks"]],
            warnings=[DEMO_ALERT])

    def _propose(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        p = self._tool("propose_inspection", field=field)
        if "error" in p or "message" in p:
            return self._error(p.get("error") or p["message"])
        t = ProposedTask(**p["proposed_task"])
        return CopilotAnswer(
            summary=f"I drafted an inspection for {t.field_code}. Review it and confirm to create the task.",
            evidence=[t.instructions], confidence="moderate",
            missing_data=["Your confirmation (the task has not been saved yet)"],
            next_action="Confirm the task below.", proposed_task=t,
            sources=[Source(type="assessment", label=f"{t.field_code} assessment", ref=f"risk_assessment:{t.assessment_id}")],
            warnings=[DEMO_ALERT])

    def _error(self, msg: str) -> CopilotAnswer:
        return CopilotAnswer(summary=msg, confidence="low", next_action="Rephrase mentioning the field (e.g. F04).",
                             warnings=[DEMO_ALERT])
