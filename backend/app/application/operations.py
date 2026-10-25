"""Loop operacional: tarefa → vistoria → verificação → intervenção → medição → memória.

Tudo que o usuário cria é gravado com is_synthetic=False. Observações pós-intervenção geradas pela demo são
marcadas com source='simulacao_pos_intervencao' e is_synthetic=True.
"""
import base64
import io
import os
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field as PField
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.application import map_service
from app.application.map_service import NotFound
from app.core.fmt import br
from app.infrastructure.db.models import (
    CropSeason, Field, Inspection, Intervention, MemoryEvent, Observation, OutcomeMeasurement, RiskAssessment, Task,
)
from app.infrastructure.seed.scenario import ndvi_curve

SIM_SOURCE = "simulacao_pos_intervencao"
STATUSES = ("pendente", "atribuída", "em_andamento", "concluída", "verificada")
TRANSITIONS = {
    "pendente": {"atribuída", "em_andamento"},
    "atribuída": {"pendente", "em_andamento"},
    "em_andamento": {"atribuída"},          # concluir exige registrar a vistoria
    "concluída": {"em_andamento"},          # verificar exige agrônomo
    "verificada": set(),
}
CHEMICAL = re.compile(r"(defensiv|inseticid|fungicid|herbicid|acaricid|agrot[oó]xic|pulveriza|l/ha|ml/ha|g/ha|dose)", re.I)
RECEITUARIO = "Requer receituário e validação de engenheiro agrônomo."
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "media"))


class InvalidOperation(Exception):
    pass


# ------------------------------------------------------------------ schemas
class TaskCreate(BaseModel):
    field_id: int
    assessment_id: int | None = None
    title: str = PField(min_length=3, max_length=160)
    kind: str = "vistoria"
    priority: str = PField(default="alta", pattern="^(alta|media|baixa)$")
    assignee: str | None = None
    due_date: date | None = None
    instructions: str | None = None
    source: str = PField(default="manual", description="manual | copiloto | mapa")


class StatusChange(BaseModel):
    status: str


class InspectionIn(BaseModel):
    findings: str = PField(min_length=5)
    verified_cause: str | None = None
    notes: str | None = None
    recorded_by: str = PField(min_length=2)
    inspected_at: date | None = None
    photos: list[str] = PField(default_factory=list, description="data URLs (image/jpeg|png), máx. 6")


class VerifyIn(BaseModel):
    verified_by: str = PField(min_length=2)
    notes: str | None = None


class InterventionIn(BaseModel):
    field_id: int
    inspection_id: int | None = None
    recommended_action: str | None = None
    approved_action: str = PField(min_length=5)
    approved_by: str = PField(min_length=2)
    executed_at: date | None = None
    actual_cost: float = PField(ge=0)
    notes: str | None = None
    receituario_confirmado: bool = False


# ------------------------------------------------------------------ helpers
def _season(s: Session, farm_id: int) -> CropSeason:
    return s.scalars(select(CropSeason).where(CropSeason.farm_id == farm_id, CropSeason.is_current.is_(True))).one()


def _memory(s: Session, field: Field, d: date, typ: str, title: str, summary: str, refs: dict, synthetic=False):
    s.add(MemoryEvent(field_id=field.id, season_id=_season(s, field.farm_id).id, date=d, type=typ, title=title,
                      summary=summary, refs=refs, is_synthetic=synthetic))


def _save_photo(data_url: str) -> str:
    m = re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", data_url, re.S)
    if not m:
        raise InvalidOperation("Foto inválida: envie imagem JPEG, PNG ou WebP")
    raw = base64.b64decode(m.group(2))
    if len(raw) > 4_000_000:
        raise InvalidOperation("Foto acima de 4 MB")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{'jpg' if m.group(1) in ('jpeg', 'jpg') else m.group(1)}"
    (MEDIA_DIR / name).write_bytes(raw)
    return f"/media/{name}"


def _insp_dict(i: Inspection | None) -> dict | None:
    if not i:
        return None
    return dict(id=i.id, inspected_at=i.inspected_at, findings=i.findings, verified_cause=i.verified_cause,
                photos=i.photos, notes=i.notes, recorded_by=i.recorded_by)


def _outcome_dict(o: OutcomeMeasurement | None) -> dict | None:
    if not o:
        return None
    return dict(id=o.id, intervention_id=o.intervention_id, metric=o.metric, before_start=o.before_start,
                before_end=o.before_end, after_start=o.after_start, after_end=o.after_end, before_value=o.before_value,
                after_value=o.after_value, comparison_before=o.comparison_before, comparison_after=o.comparison_after,
                delta=o.delta, delta_vs_comparison=o.delta_vs_comparison, method=o.method,
                comparison_area=o.comparison_area, limitations=o.limitations, confidence=o.confidence,
                is_synthetic=o.is_synthetic)


def _interv_dict(s: Session, i: Intervention) -> dict:
    o = s.scalars(select(OutcomeMeasurement).where(OutcomeMeasurement.intervention_id == i.id)).first()
    return dict(id=i.id, field_id=i.field_id, inspection_id=i.inspection_id, recommended_action=i.recommended_action,
                approved_action=i.approved_action, approved_by=i.approved_by, executed_at=i.executed_at,
                actual_cost=i.actual_cost, notes=i.notes, is_synthetic=i.is_synthetic, outcome=_outcome_dict(o))


def task_dict(s: Session, t: Task, detail: bool = False) -> dict:
    f = s.get(Field, t.field_id)
    insp = s.scalars(select(Inspection).where(Inspection.task_id == t.id)).first()
    d = dict(id=t.id, field_id=t.field_id, field_code=f.code, field_name=f.name, assessment_id=t.assessment_id,
             title=t.title, kind=t.kind, priority=t.priority, assignee=t.assignee, due_date=t.due_date,
             instructions=t.instructions, status=t.status, created_at=t.created_at, updated_at=t.updated_at,
             is_synthetic=t.is_synthetic, has_inspection=insp is not None,
             verified_cause=insp.verified_cause if insp else None)
    if detail:
        d["inspection"] = _insp_dict(insp)
        d["interventions"] = [_interv_dict(s, i) for i in s.scalars(
            select(Intervention).where(Intervention.inspection_id == insp.id).order_by(Intervention.id))] if insp else []
        ra = s.get(RiskAssessment, t.assessment_id) if t.assessment_id else None
        d["assessment"] = dict(id=ra.id, date=ra.date, level=ra.level, affected_ha=ra.affected_ha,
                               observation=ra.details.get("observation"), next_step=ra.details.get("next_step"),
                               hypotheses=[dict(cause=h.cause, confidence=h.confidence) for h in ra.hypotheses]) if ra else None
        d["geometry"] = s.execute(text("SELECT ST_AsGeoJSON(geom, 6)::json FROM tasks WHERE id=:i"), {"i": t.id}).scalar()
        prior = s.execute(select(Intervention).join(Inspection, Inspection.id == Intervention.inspection_id).join(
            Task, Task.id == Inspection.task_id).where(Task.field_id == t.field_id, Task.id != t.id)
            .order_by(Intervention.executed_at.desc())).scalars().first()
        d["previous_intervention"] = dict(executed_at=prior.executed_at, approved_action=prior.approved_action,
                                          actual_cost=prior.actual_cost) if prior else None
        d["status_flow"] = list(STATUSES)
    return d


# ------------------------------------------------------------------ tarefas
def create_task(s: Session, data: TaskCreate) -> dict:
    field = s.get(Field, data.field_id)
    if not field:
        raise NotFound("Talhão não encontrado")
    geom, ra = None, None
    if data.assessment_id:
        ra = s.get(RiskAssessment, data.assessment_id)
        if not ra or ra.field_id != field.id:
            raise NotFound("Avaliação não encontrada para este talhão")
        geom = ra.geom
    t = Task(farm_id=field.farm_id, field_id=field.id, assessment_id=data.assessment_id, title=data.title,
             kind=data.kind, priority=data.priority, assignee=data.assignee, due_date=data.due_date,
             instructions=data.instructions, status="atribuída" if data.assignee else "pendente", geom=geom,
             is_synthetic=False)
    s.add(t)
    s.flush()
    ref = field.farm.reference_date
    if ra:  # registra a anomalia atual na memória uma única vez
        exists = s.scalars(select(MemoryEvent).where(MemoryEvent.field_id == field.id, MemoryEvent.type == "anomalia",
                                                     MemoryEvent.date == ra.date)).first()
        if not exists:
            top = ra.hypotheses[0] if ra.hypotheses else None
            _memory(s, field, ra.date, "anomalia", "Anomalia detectada pelo monitoramento",
                    f"{ra.details.get('observation', '')} Hipótese principal: "
                    f"{top.cause.lower() if top else '—'} (confiança {top.confidence if top else '—'}).",
                    {"assessment_id": ra.id}, synthetic=True)
    _memory(s, field, ref, "tarefa", f"Vistoria criada: {data.title}",
            f"Origem: {data.source}. Responsável: {data.assignee or 'a definir'}. {data.instructions or ''}".strip(),
            {"task_id": t.id, "assessment_id": data.assessment_id})
    s.commit()
    s.refresh(t)
    return task_dict(s, t)


def list_tasks(s: Session, status: str | None = None, field_id: int | None = None) -> list[dict]:
    q = select(Task).order_by(Task.created_at.desc(), Task.id.desc())
    if status:
        q = q.where(Task.status == status)
    if field_id:
        q = q.where(Task.field_id == field_id)
    return [task_dict(s, t) for t in s.scalars(q)]


def get_task(s: Session, task_id: int) -> dict:
    t = s.get(Task, task_id)
    if not t:
        raise NotFound("Tarefa não encontrada")
    return task_dict(s, t, detail=True)


def change_status(s: Session, task_id: int, new: str) -> dict:
    t = s.get(Task, task_id)
    if not t:
        raise NotFound("Tarefa não encontrada")
    if new not in TRANSITIONS.get(t.status, set()):
        raise InvalidOperation(f"Não é possível mudar de '{t.status}' para '{new}'")
    t.status = new
    s.commit()
    return get_task(s, task_id)


def record_inspection(s: Session, task_id: int, data: InspectionIn) -> dict:
    t = s.get(Task, task_id)
    if not t:
        raise NotFound("Tarefa não encontrada")
    if t.status in ("concluída", "verificada"):
        raise InvalidOperation("Vistoria já registrada para esta tarefa")
    if len(data.photos) > 6:
        raise InvalidOperation("Máximo de 6 fotos")
    field = s.get(Field, t.field_id)
    photos = [_save_photo(p) for p in data.photos]
    i = Inspection(task_id=t.id, inspected_at=data.inspected_at or field.farm.reference_date, findings=data.findings,
                   verified_cause=data.verified_cause or None, photos=photos, notes=data.notes,
                   recorded_by=data.recorded_by, is_synthetic=False)
    s.add(i)
    t.status = "concluída"
    s.flush()
    cause = f"Causa verificada: {data.verified_cause}. " if data.verified_cause else "Causa não confirmada. "
    _memory(s, field, i.inspected_at, "vistoria",
            f"Vistoria {'confirmou ' + data.verified_cause.lower() if data.verified_cause else 'registrada'}",
            f"{cause}{data.findings}" + (f" ({len(photos)} foto(s))" if photos else ""),
            {"task_id": t.id, "inspection_id": i.id})
    s.commit()
    return get_task(s, task_id)


def verify_task(s: Session, task_id: int, data: VerifyIn) -> dict:
    t = s.get(Task, task_id)
    if not t:
        raise NotFound("Tarefa não encontrada")
    if t.status != "concluída":
        raise InvalidOperation("Só é possível verificar tarefas com vistoria concluída")
    t.status = "verificada"
    insp = s.scalars(select(Inspection).where(Inspection.task_id == t.id)).one()
    if data.notes:
        insp.notes = f"{insp.notes or ''}\nVerificação ({data.verified_by}): {data.notes}".strip()
    s.commit()
    return get_task(s, task_id)


# ------------------------------------------------------------------ intervenção
def create_intervention(s: Session, data: InterventionIn) -> dict:
    field = s.get(Field, data.field_id)
    if not field:
        raise NotFound("Talhão não encontrado")
    insp = s.get(Inspection, data.inspection_id) if data.inspection_id else None
    if data.inspection_id and not insp:
        raise NotFound("Vistoria não encontrada")
    if insp:
        task = s.get(Task, insp.task_id)
        if task.field_id != field.id:
            raise InvalidOperation("A vistoria pertence a outro talhão")
        if task.status != "verificada":
            raise InvalidOperation("A vistoria precisa ser verificada por agrônomo antes de aprovar a intervenção")
    if CHEMICAL.search(data.approved_action) and not data.receituario_confirmado:
        raise InvalidOperation(f"Intervenção com produto químico. {RECEITUARIO} Confirme o receituário.")
    i = Intervention(field_id=field.id, inspection_id=data.inspection_id, recommended_action=data.recommended_action,
                     approved_action=data.approved_action, approved_by=data.approved_by,
                     executed_at=data.executed_at or field.farm.reference_date, actual_cost=data.actual_cost,
                     notes=data.notes, is_synthetic=False)
    s.add(i)
    s.flush()
    _memory(s, field, i.executed_at, "intervencao", "Intervenção aprovada e executada",
            f"{data.approved_action} Aprovada por {data.approved_by}. Custo realizado: R$ {br(data.actual_cost, 2)}."
            + (f" {RECEITUARIO}" if CHEMICAL.search(data.approved_action) else ""),
            {"intervention_id": i.id, "inspection_id": data.inspection_id})
    s.commit()
    return _interv_dict(s, i)


# ------------------------------------------------------------------ simulação + medição de resultado
def _zone_and_comparison(s: Session, field: Field, assessment_id: int | None) -> tuple[list[int], list[int]]:
    ids = s.execute(text("""
        SELECT c.id, CASE WHEN ra.geom IS NOT NULL AND ST_Intersects(ST_PointOnSurface(c.geom), ra.geom) THEN 1 ELSE 0 END z
        FROM management_cells c LEFT JOIN risk_assessments ra ON ra.id = :ra
        WHERE c.field_id = :f ORDER BY c.id
    """), {"f": field.id, "ra": assessment_id}).all()
    zone = [r.id for r in ids if r.z]
    comp = [r.id for r in ids if not r.z]
    return zone, comp


def _window_mean(s: Session, cells: list[int], start: date, end: date) -> tuple[float, int]:
    r = s.execute(text("""
        SELECT avg(ndvi), count(DISTINCT date) FROM observations
        WHERE cell_id = ANY(:c) AND date BETWEEN :a AND :b AND NOT cloud_flag
    """), {"c": cells, "a": start, "b": end}).one()
    return float(r[0]) if r[0] is not None else float("nan"), int(r[1])


def simulate_and_measure(s: Session, intervention_id: int) -> dict:
    i = s.get(Intervention, intervention_id)
    if not i:
        raise NotFound("Intervenção não encontrada")
    field = s.get(Field, i.field_id)
    farm = field.farm
    season = _season(s, farm.id)
    insp = s.get(Inspection, i.inspection_id) if i.inspection_id else None
    task = s.get(Task, insp.task_id) if insp else None
    zone, comp = _zone_and_comparison(s, field, task.assessment_id if task else None)
    if not zone:
        raise InvalidOperation("Intervenção sem zona de anomalia associada (crie a tarefa a partir de uma avaliação)")

    # remove simulação anterior e resultado anterior desta intervenção
    s.execute(delete(Observation).where(Observation.season_id == season.id, Observation.source == SIM_SOURCE))
    s.execute(delete(OutcomeMeasurement).where(OutcomeMeasurement.intervention_id == i.id))

    last = s.execute(text("SELECT max(date), max(das) FROM observations WHERE season_id=:s AND source <> :src"),
                     {"s": season.id, "src": SIM_SOURCE}).one()
    d0, das0 = last[0], int(last[1])
    cur = s.execute(text("""
        SELECT o.cell_id, o.ndvi FROM observations o JOIN management_cells c ON c.id=o.cell_id JOIN fields f ON f.id=c.field_id
        WHERE o.season_id=:s AND o.date=:d AND f.farm_id=:farm ORDER BY o.cell_id
    """), {"s": season.id, "d": d0, "farm": farm.id}).all()
    ids = np.array([r.cell_id for r in cur])
    v0 = np.array([r.ndvi for r in cur], dtype=float)
    base = dict(s.execute(text("""
        SELECT o.cell_id, avg(o.ndvi) FROM observations o JOIN crop_seasons cs ON cs.id=o.season_id
        WHERE cs.farm_id=:f AND cs.sowing_date < :sow AND o.das=:das AND NOT o.cloud_flag GROUP BY o.cell_id
    """), {"f": farm.id, "sow": season.sowing_date, "das": das0}).all())
    baseline = np.array([base.get(c, np.nan) for c in ids], dtype=float)
    in_zone = np.isin(ids, zone)
    deficit = np.where(in_zone, np.clip(np.nan_to_num(baseline - v0), 0, None), 0.0)

    cause = (insp.verified_cause or "").lower() if insp else ""
    recovery = 0.7 if "hídric" in cause or "hidric" in cause else 0.35 if cause else 0.25
    rng = np.random.default_rng(1000 + i.id)
    buf = io.StringIO()
    sim_dates = []
    for step in (1, 2, 3):
        das = das0 + 5 * step
        d = d0 + timedelta(days=5 * step)
        sim_dates.append(d)
        t_days = max(0, (d - i.executed_at).days)
        k = recovery * (1 - np.exp(-t_days / 5))
        v = v0 + (ndvi_curve(das) - ndvi_curve(das0)) + k * deficit + rng.normal(0, 0.008, v0.size)
        v = np.clip(v, -0.1, 0.95)
        ndre = 0.08 + 0.62 * (v - 0.18) + rng.normal(0, 0.006, v.size)
        for cid, a, b in zip(ids, v, ndre):
            buf.write(f"{cid}\t{season.id}\t{d.isoformat()}\t{das}\t{a:.4f}\t{b:.4f}\tf\t{SIM_SOURCE}\tt\n")
    buf.seek(0)
    with s.connection().connection.cursor().copy(
        "COPY observations (cell_id, season_id, date, das, ndvi, ndre, cloud_flag, source, is_synthetic) FROM STDIN"
    ) as cp:
        cp.write(buf.read())
    s.flush()

    bf, bt = i.executed_at - timedelta(days=4), i.executed_at  # última cena antes da intervenção
    af, at = sim_dates[0], sim_dates[-1]
    b, nb = _window_mean(s, zone, bf, bt)
    a, _ = _window_mean(s, zone, af, at)
    cb, _ = _window_mean(s, comp, bf, bt)
    ca, _ = _window_mean(s, comp, af, at)
    did = (a - b) - (ca - cb)
    conf = "moderada" if insp and insp.verified_cause and len(comp) > 50 and nb >= 1 else "baixa"
    o = OutcomeMeasurement(
        intervention_id=i.id, metric="ndvi", before_start=bf, before_end=bt, after_start=af, after_end=at,
        before_value=round(b, 3), after_value=round(a, 3), comparison_before=round(cb, 3), comparison_after=round(ca, 3),
        delta=round(a - b, 3), delta_vs_comparison=round(did, 3),
        method="Diferença-em-diferenças simples: variação do NDVI médio da zona tratada entre as janelas antes e depois, "
               "descontada a variação da área de comparação no mesmo período. Observações com nuvem descartadas.",
        comparison_area=f"Restante do {field.name} fora da zona em anomalia ({len(comp)} células, mesma cultivar e semeadura).",
        limitations="Observações pós-intervenção SIMULADAS para demonstração (não são medições de satélite). "
                    "Senescência natural reduz o NDVI de toda a lavoura no fim do ciclo (por isso a comparação é pela diferença em "
                    "relação à área de referência); sem parcela-controle sem intervenção; "
                    "sem dados de clima no período pós-intervenção. Indica associação, não prova causal.",
        confidence=conf, is_synthetic=True,
    )
    s.add(o)
    s.flush()
    sign = "+" if did >= 0 else "−"
    _memory(s, field, at, "resultado", "Resultado medido após a intervenção (simulado)",
            f"NDVI da zona: {br(b, 2)} → {br(a, 2)}; área de comparação: {br(cb, 2)} → {br(ca, 2)}. "
            f"Diferença líquida {sign}{br(abs(did), 2)}. Observações pós-intervenção simuladas — associação, não prova causal.",
            {"intervention_id": i.id, "outcome_id": o.id}, synthetic=True)
    s.commit()
    map_service.clear_cache()
    return outcome_detail(s, o.id)


def list_outcomes(s: Session) -> list[dict]:
    rows = s.execute(select(OutcomeMeasurement, Intervention, Field).join(
        Intervention, Intervention.id == OutcomeMeasurement.intervention_id).join(Field, Field.id == Intervention.field_id)
        .order_by(Intervention.executed_at.desc())).all()
    return [dict(**_outcome_dict(o), field_id=f.id, field_code=f.code, field_name=f.name,
                 executed_at=i.executed_at, approved_action=i.approved_action, actual_cost=i.actual_cost,
                 user_created=not i.is_synthetic) for o, i, f in rows]


def outcome_detail(s: Session, outcome_id: int) -> dict:
    o = s.get(OutcomeMeasurement, outcome_id)
    if not o:
        raise NotFound("Resultado não encontrado")
    i = s.get(Intervention, o.intervention_id)
    field = s.get(Field, i.field_id)
    insp = s.get(Inspection, i.inspection_id) if i.inspection_id else None
    task = s.get(Task, insp.task_id) if insp else None
    zone, comp = _zone_and_comparison(s, field, task.assessment_id if task else None)
    if not zone:  # resultado histórico do seed: zona = setor sudoeste (geometria da tarefa)
        zone_ids = s.execute(text("""
            SELECT c.id FROM management_cells c JOIN tasks t ON t.id=:t
            WHERE c.field_id=:f AND ST_Intersects(ST_PointOnSurface(c.geom), t.geom)
        """), {"t": task.id if task else -1, "f": field.id}).scalars().all()
        zone = list(zone_ids)
        comp = [c for c in s.execute(text("SELECT id FROM management_cells WHERE field_id=:f"), {"f": field.id}).scalars()
                if c not in set(zone)]
    season_id = s.execute(text("SELECT id FROM crop_seasons WHERE farm_id=:farm AND sowing_date<=:d ORDER BY sowing_date DESC LIMIT 1"),
                          {"farm": field.farm_id, "d": i.executed_at}).scalar()
    series = s.execute(text("""
        SELECT o.date, o.das, bool_or(o.source = :src) simulated,
               avg(o.ndvi) FILTER (WHERE o.cell_id = ANY(:z) AND NOT o.cloud_flag) zone,
               avg(o.ndvi) FILTER (WHERE o.cell_id = ANY(:c) AND NOT o.cloud_flag) comparison
        FROM observations o WHERE o.season_id=:s AND o.cell_id = ANY(:all) AND o.date >= :from
        GROUP BY o.date, o.das ORDER BY o.date
    """), {"src": SIM_SOURCE, "z": zone, "c": comp, "s": season_id, "all": zone + comp,
           "from": i.executed_at - timedelta(days=30)}).all()
    return dict(
        outcome=_outcome_dict(o), field_id=field.id, field_code=field.code, field_name=field.name, farm_id=field.farm_id,
        intervention=_interv_dict(s, i), inspection=_insp_dict(insp),
        task=dict(id=task.id, title=task.title) if task else None, zone_cells=len(zone), comparison_cells=len(comp),
        zone_cell_ids=zone,
        series=[dict(date=r.date, das=r.das, simulated=r.simulated, zone=r.zone and round(r.zone, 3),
                     comparison=r.comparison and round(r.comparison, 3)) for r in series],
        before_date=s.execute(text("SELECT max(date) FROM observations WHERE season_id=:s AND date<=:d AND NOT cloud_flag"),
                              {"s": season_id, "d": o.before_end}).scalar(),
        after_date=o.after_end,
        disclaimer="Resultado indica associação, não prova causal. Não representa economia realizada.",
    )


# ------------------------------------------------------------------ reset da demo
def reset_demo(s: Session) -> dict:
    """Remove tudo que foi criado durante a demonstração; mantém o cenário sintético original."""
    n_tasks = s.execute(delete(Task).where(Task.is_synthetic.is_(False))).rowcount
    s.execute(delete(Intervention).where(Intervention.is_synthetic.is_(False)))
    s.execute(delete(MemoryEvent).where(MemoryEvent.is_synthetic.is_(False)))
    s.execute(delete(MemoryEvent).where(MemoryEvent.type.in_(("anomalia", "resultado")),
                                        MemoryEvent.refs["assessment_id"].as_string().is_not(None)
                                        | MemoryEvent.refs["outcome_id"].as_string().is_not(None)))
    n_obs = s.execute(delete(Observation).where(Observation.source == SIM_SOURCE)).rowcount
    s.execute(text("DELETE FROM risk_assessments ra USING fields f, farms fa WHERE ra.field_id=f.id AND f.farm_id=fa.id "
                   "AND ra.date > fa.reference_date"))
    s.commit()
    map_service.clear_cache()
    return {"tarefas_removidas": n_tasks, "observacoes_simuladas_removidas": n_obs}
