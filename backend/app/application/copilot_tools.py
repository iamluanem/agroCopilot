"""Ferramentas do copiloto. Leem dados reais do app; nenhuma grava sem confirmação do usuário."""
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
        raise NotFound("Informe o talhão (ex.: T04)")
    fields = ctx.farm.fields
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit() and int(ref) > 20):
        f = next((x for x in fields if x.id == int(ref)), None)
        if f:
            return f
    m = re.search(r"(\d{1,2})", str(ref))
    if m:
        code = f"T{int(m.group(1)):02d}"
        f = next((x for x in fields if x.code == code), None)
        if f:
            return f
    raise NotFound(f"Talhão '{ref}' não encontrado. Disponíveis: {', '.join(x.code for x in fields)}")


def _trim_assessment(a: dict) -> dict:
    keep = ("field_id", "code", "name", "area_ha", "date", "das", "stage", "level", "red_ha", "yellow_ha",
            "ndvi_mean", "ndvi_baseline", "assessment_id", "has_zone", "summary", "confidence", "observation",
            "pattern_label", "onset_das", "onset_date", "ndvi_drop", "recurrence_share", "weather", "urgency",
            "urgency_reason", "worsening", "priority_score", "next_step", "prior_verified", "hypotheses", "economics",
            "rank")
    return {k: a[k] for k in keep if k in a}


# ------------------------------------------------------------------ ferramentas
def get_farm_summary(ctx: ToolContext) -> dict:
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    pr = intel.priorities(ctx.s, ctx.farm.id, ctx.ref)
    return dict(
        fazenda=ctx.farm.name, municipio=f"{ctx.farm.municipality}-{ctx.farm.state}", cultura=ctx.farm.crop,
        data_referencia=ctx.ref, das=snap["das"], estadio=eco.soybean_stage(snap["das"]), safra=snap["season_name"],
        area_total_ha=snap["summary"]["total_ha"], pct_por_nivel=snap["summary"]["pct_by_level"],
        area_por_nivel_ha=snap["summary"]["area_by_level"], exposicao_total=pr["totals"],
        prioridades=[dict(rank=i["rank"], talhao=i["code"], nome=i["name"], nivel=i["level"], area_critica_ha=i["red_ha"],
                          area_atencao_ha=i["yellow_ha"], hipotese_principal=(i["hypotheses"][0]["cause"] if i["hypotheses"] else None),
                          confianca_hipotese=(i["hypotheses"][0]["confidence"] if i["hypotheses"] else None),
                          exposicao_min=(i["economics"] or {}).get("exposure_min"),
                          exposicao_max=(i["economics"] or {}).get("exposure_max"),
                          assessment_id=i["assessment_id"], proxima_acao=i.get("next_step")) for i in pr["items"]],
        formula_prioridade=pr["priority_formula"], dados_sinteticos=True,
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
        raise NotFound(f"Célula {cell_id} não encontrada")
    f = ctx.s.get(Field, rows[0].field_id)
    by_season: dict[str, list] = {}
    for r in rows:
        by_season.setdefault(r.season, []).append(dict(das=r.das, ndvi=None if r.cloud_flag else round(r.ndvi, 3)))
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    i = snap["cells"]["id"].index(cell_id)
    return dict(cell_id=cell_id, talhao=f.code, nivel_atual=snap["levels"][snap["cells"]["level"][i]],
                score=snap["cells"]["score"][i], ndvi_atual=snap["cells"]["ndvi"][i],
                historico_mesmo_das=snap["cells"]["baseline"][i], series=by_season, dados_sinteticos=True)


def compare_fields(ctx: ToolContext, fields: list[str] | None = None) -> dict:
    snap = risk_snapshot(ctx.farm.id, ctx.ref)
    wanted = {resolve_field(ctx, x).id for x in fields} if fields else None
    return dict(data=ctx.ref, talhoes=[
        dict(talhao=f["code"], nivel=f["level"], ndvi_medio=f["ndvi_mean"], ndvi_historico=f["ndvi_baseline"],
             area_critica_ha=f["area_by_level"]["vermelho"], area_atencao_ha=f["area_by_level"]["amarelo"],
             nuvem_pct=f["cloud_pct"])
        for f in snap["fields"] if wanted is None or f["field_id"] in wanted
    ])


def get_weather(ctx: ToolContext, days: int = 30) -> dict:
    days = max(7, min(int(days), 120))
    rows = intel.weather(ctx.s, ctx.farm.id, ctx.ref - timedelta(days=days - 1), ctx.ref)
    season = next(x for x in ctx.farm.seasons if x.is_current)
    w = intel._weather_context(ctx.s, ctx.farm.id, ctx.ref, season.sowing_date)
    return dict(periodo_dias=days, chuva_total_mm=round(sum(r["rain_mm"] for r in rows), 1),
                maior_sequencia_sem_chuva_dias=w["max_dry_days"], seca_inicio=w["dry_start"], seca_fim=w["dry_end"],
                tmax_media_no_periodo_seco=w["tmax_dry_mean"] and round(w["tmax_dry_mean"], 1),
                chuva_ultimos_21d_mm=w["rain_21d_mm"], dados_sinteticos=True,
                diario=[dict(data=r["date"], chuva_mm=r["rain_mm"], tmax=r["tmax_c"]) for r in rows[-14:]])


def get_memory(ctx: ToolContext, field: str, query: str | None = None) -> dict:
    f = resolve_field(ctx, field)
    events = intel.memory(ctx.s, f.id, query) if query else intel.memory(ctx.s, f.id)
    if query and not events:  # busca vazia: devolve a memória toda para o modelo decidir
        events = intel.memory(ctx.s, f.id)
    return dict(talhao=f.code, eventos=[e for e in events if e["type"] != "safra" or not query][:30],
                dados_sinteticos=True)


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
        out.append(dict(id=t.id, talhao=f.code, titulo=t.title, status=t.status, prioridade=t.priority,
                        responsavel=t.assignee, prazo=t.due_date,
                        vistoria=dict(data=insp.inspected_at, causa_verificada=insp.verified_cause,
                                      achados=insp.findings) if insp else None))
    return dict(tarefas=out, abertas=sum(1 for t in out if t["status"] not in ("concluída", "verificada")))


def estimate_economics(ctx: ToolContext, field: str, preco_saca_rs: float | None = None,
                       produtividade_esperada_sc_ha: float | None = None) -> dict:
    a = get_field_risk(ctx, field)
    if not a["has_zone"]:
        return dict(talhao=a["code"], mensagem=a["summary"])
    base = intel.get_assumptions(ctx.s)
    over = {k: v for k, v in dict(preco_saca_rs=preco_saca_rs,
                                  produtividade_esperada_sc_ha=produtividade_esperada_sc_ha).items() if v}
    if not over:  # sem simulação: devolve exatamente o registro persistido da avaliação
        x = a["economics"]
        return dict(talhao=a["code"], assessment_id=a["assessment_id"], simulacao=False,
                    area_afetada_ha=x["affected_ha"], exposicao_min=x["exposure_min"], exposicao_max=x["exposure_max"],
                    custo_vistoria=x["inspection_cost"], custo_intervencao_estimado=x["intervention_cost"],
                    valor_bruto_area=x["gross_value_rs"], formula=x["formula"], premissas=x["assumptions"],
                    rotulo=x["label"])
    p = a["economics"]["assumptions"]
    assumptions = eco.EconomicAssumptions(**{**base.__dict__, **over})
    e = eco.estimate_exposure(p["area_critica_ha"], p["area_atencao_ha"], assumptions)
    return dict(talhao=a["code"], assessment_id=a["assessment_id"], simulacao=bool(over),
                area_afetada_ha=e.affected_ha, exposicao_min=e.exposure_min, exposicao_max=e.exposure_max,
                custo_vistoria=e.inspection_cost, custo_intervencao_estimado=e.intervention_cost,
                valor_bruto_area=e.gross_value_rs, formula=e.formula, premissas=e.assumptions,
                rotulo="Exposição estimada — não é perda confirmada nem economia realizada")


def get_intervention_outcomes(ctx: ToolContext, field: str) -> dict:
    f = resolve_field(ctx, field)
    rows = ctx.s.execute(select(Intervention, OutcomeMeasurement).outerjoin(
        OutcomeMeasurement, OutcomeMeasurement.intervention_id == Intervention.id,
    ).where(Intervention.field_id == f.id).order_by(Intervention.executed_at.desc())).all()
    seasons = sorted(ctx.farm.seasons, key=lambda x: x.sowing_date)
    safra = lambda d: next((x.name for x in reversed(seasons) if x.sowing_date <= d), None)
    current = next(x.name for x in seasons if x.is_current)
    return dict(talhao=f.code, safra_atual=current, intervencoes=[dict(
        id=i.id, safra=safra(i.executed_at), executada_em=i.executed_at, acao_aprovada=i.approved_action,
        aprovada_por=i.approved_by, observacoes_pos_simuladas=bool(o and not i.is_synthetic),
        custo_realizado=i.actual_cost,
        resultado=dict(metrica=o.metric, antes=o.before_value, depois=o.after_value,
                       comparacao_antes=o.comparison_before, comparacao_depois=o.comparison_after,
                       delta=o.delta, delta_liquido_vs_comparacao=o.delta_vs_comparison, metodo=o.method,
                       area_comparacao=o.comparison_area, limitacoes=o.limitations, confianca=o.confidence,
                       janela_antes=[o.before_start, o.before_end], janela_depois=[o.after_start, o.after_end])
        if o else None) for i, o in rows], dados_sinteticos=True)


def propose_inspection(ctx: ToolContext, field: str) -> dict:
    a = get_field_risk(ctx, field)
    if not a["has_zone"]:
        return dict(talhao=a["code"], mensagem="Sem zona em anomalia que justifique vistoria agora.")
    top = a["hypotheses"][0]
    checklist = "; ".join(m for h in a["hypotheses"][:2] for m in h["missing"])
    return dict(tarefa_proposta=dict(
        field_id=a["field_id"], field_code=a["code"], assessment_id=a["assessment_id"],
        title=f"Vistoria — zona em anomalia do {a['name']} ({a['red_ha']:.0f} ha críticos)".replace(".", ","),
        priority="alta" if a["red_ha"] >= 10 else "media", assignee="Carlos Menezes (técnico de campo)",
        due_date=(ctx.ref + timedelta(days=2)).isoformat(),
        instructions=f"Hipótese principal: {top['cause']} (confiança {top['confidence']}). Verificar: {checklist}. "
                     "Registrar fotos georreferenciadas e a causa verificada.",
    ), observacao="Proposta não gravada. Requer confirmação do usuário.")


# ------------------------------------------------------------------ registro
FIELD_ARG = {"type": "string", "description": "Código do talhão, ex.: T04"}
TOOLS: dict[str, tuple[Callable, str, dict]] = {
    "get_farm_summary": (get_farm_summary, "Resumo da fazenda na data de referência: % por nível de risco, exposição "
                         "total e talhões ranqueados por prioridade.", {"type": "object", "properties": {}}),
    "get_field_risk": (get_field_risk, "Avaliação de um talhão: zona em anomalia, observação, hipóteses com evidências e "
                       "dado faltante, exposição em R$, urgência e próxima ação.",
                       {"type": "object", "properties": {"field": FIELD_ARG, "date_": {"type": "string",
                        "description": "Data AAAA-MM-DD (opcional; padrão = referência)"}}, "required": ["field"]}),
    "get_cell_history": (get_cell_history, "Série de NDVI de uma célula de manejo por safra e seu risco atual.",
                         {"type": "object", "properties": {"cell_id": {"type": "integer"}}, "required": ["cell_id"]}),
    "compare_fields": (compare_fields, "Compara NDVI atual, histórico e áreas em anomalia entre talhões.",
                       {"type": "object", "properties": {"fields": {"type": "array", "items": FIELD_ARG}}}),
    "get_weather": (get_weather, "Chuva e temperatura recentes (sintéticas) e maior sequência sem chuva.",
                    {"type": "object", "properties": {"days": {"type": "integer", "minimum": 7, "maximum": 120}}}),
    "get_memory": (get_memory, "Memória agronômica do talhão: anomalias, vistorias, intervenções e resultados anteriores.",
                   {"type": "object", "properties": {"field": FIELD_ARG, "query": {"type": "string"}}, "required": ["field"]}),
    "list_tasks": (list_tasks, "Lista tarefas operacionais (vistorias) com status e achados.",
                   {"type": "object", "properties": {"field": FIELD_ARG, "status": {"type": "string"}}}),
    "estimate_economics": (estimate_economics, "Exposição econômica estimada do talhão, com premissas; permite simular "
                           "preço da saca ou produtividade.",
                           {"type": "object", "properties": {"field": FIELD_ARG, "preco_saca_rs": {"type": "number"},
                            "produtividade_esperada_sc_ha": {"type": "number"}}, "required": ["field"]}),
    "get_intervention_outcomes": (get_intervention_outcomes, "Intervenções registradas no talhão e resultado medido "
                                  "(antes/depois, área de comparação, método, limitações).",
                                  {"type": "object", "properties": {"field": FIELD_ARG}, "required": ["field"]}),
    "propose_inspection": (propose_inspection, "Monta uma proposta de vistoria para a zona em anomalia. NÃO grava: o "
                           "usuário confirma na tela.",
                           {"type": "object", "properties": {"field": FIELD_ARG}, "required": ["field"]}),
}


def run_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"erro": f"Ferramenta desconhecida: {name}"}
    fn = TOOLS[name][0]
    try:
        return _iso(fn(ctx, **(args or {})))
    except NotFound as e:
        return {"erro": str(e)}
    except TypeError as e:
        return {"erro": f"Argumentos inválidos para {name}: {e}"}
