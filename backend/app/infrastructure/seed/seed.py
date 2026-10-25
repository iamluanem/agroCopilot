"""Seed idempotente da demo. Uso: python -m app.infrastructure.seed.seed [--reset]"""
import io
import sys
import time
from datetime import timedelta

import numpy as np
from shapely import MultiPolygon, unary_union
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.fmt import br
from app.infrastructure.db.base import SessionLocal, engine
from app.infrastructure.db.models import (
    AppSetting, CropSeason, Farm, Field, Inspection, Intervention, ManagementCell, MemoryEvent,
    OutcomeMeasurement, Task,
)
from app.infrastructure.seed import scenario as sc

FARM_NAME = "Fazenda Santa Aurora"
SEED_VERSION = 4  # incremente ao mudar o cenário: o seed recria a demo automaticamente

DEFAULT_SETTINGS = {
    "economia": {
        "produtividade_esperada_sc_ha": 62.0,
        "preco_saca_rs": 120.0,
        "perda_min_pct": 8.0,
        "perda_max_pct": 25.0,
        "custo_vistoria_rs": 450.0,
        "custo_intervencao_rs_ha": 85.0,
    },
    "risco": {"limiar_amarelo": 1.5, "limiar_vermelho": 2.5, "peso_historico": 0.6},
    "fonte_dados": "demo",
    "llm_provider": "auto",  # auto = usa a chave disponível (Anthropic/OpenAI) ou o DemoProvider
}


def _wkt(g, nd=7) -> str:
    from shapely import set_precision
    return set_precision(g, 10 ** -nd).wkt


def seed(reset: bool = False) -> None:
    t0 = time.time()
    with SessionLocal() as s:
        existing = s.scalar(select(Farm).where(Farm.name == FARM_NAME))
        ver = s.get(AppSetting, "seed_version")
        prov = s.get(AppSetting, "llm_provider")
        if prov and prov.value.get("valor") == "demo" and (not ver or ver.value.get("valor", 0) < 4):
            prov.value = {"valor": "auto"}  # migração: o padrão antigo travava o copiloto no modo demo
            s.commit()
        if existing and (not ver or ver.value.get("valor") != SEED_VERSION):
            print(f"Cenário demo mudou (versão {SEED_VERSION}). Recriando…")
            reset = True
        if existing and not reset:
            print(f"Seed já aplicado (farm id={existing.id}). Use --reset para recriar.")
            return
        if existing:
            s.execute(delete(Farm).where(Farm.id == existing.id))  # cascata no banco
            s.commit()
        _seed(s)
    print(f"Seed concluído em {time.time() - t0:.1f}s")


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
        name=FARM_NAME, municipality="Sorriso", state="MT", crop="Soja", area_ha=round(total_ha, 1),
        reference_date=ref_date, is_synthetic=True,
        soil_notes="Predomínio de Latossolo Vermelho-Amarelo argiloso; setor sudoeste do T04 com textura "
                   "média a arenosa e menor retenção de água. (Dados de demonstração)",
        boundary=f"SRID=4326;{_wkt(farm_boundary)}",
    )
    s.add(farm)
    s.flush()

    seasons = []
    for spec in sc.SEASONS:
        cs = CropSeason(
            farm_id=farm.id, name=spec.name, crop="Soja", sowing_date=spec.sowing, harvest_date=spec.harvest,
            expected_yield_sc_ha=spec.expected_yield, realized_yield_sc_ha=spec.realized_yield,
            is_current=spec.is_current,
        )
        s.add(cs)
        seasons.append(cs)

    fields = []
    for i, (spec, g) in enumerate(zip(specs, fields_wgs)):
        f = Field(
            farm_id=farm.id, code=spec["code"], name=f"Talhão {spec['code'][1:]}",
            area_ha=round(float(grid.area_ha[grid.field_idx == i].sum()), 1),
            soil_texture=spec["soil"], irrigation=spec["irrigation"], boundary_source="demo_sintetico",
            geom=f"SRID=4326;{_wkt(g)}",
        )
        s.add(f)
        fields.append(f)
    s.flush()

    # células
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

    # observações via COPY
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

    # clima
    s.execute(text(
        "INSERT INTO weather_daily (farm_id, date, rain_mm, tmax_c, tmin_c, is_synthetic) "
        "VALUES (:f, :d, :r, :tx, :tn, true)"
    ), [dict(f=farm.id, d=d, r=r, tx=tx, tn=tn) for d, r, tx, tn in sc.generate_weather()])

    _seed_history(s, farm, fields, seasons, grid, obs_sets, meta)

    s.merge(AppSetting(key="seed_version", value={"valor": SEED_VERSION}))
    for k, v in DEFAULT_SETTINGS.items():
        if not s.get(AppSetting, k):  # preserva configurações editadas pelo usuário
            s.add(AppSetting(key=k, value=v if isinstance(v, dict) else {"valor": v}))
    s.commit()
    s.execute(text("ANALYZE observations"))
    s.commit()


def _seed_history(s, farm, fields, seasons, grid, obs_sets, meta) -> None:
    """Ciclo completo da safra 2024/25 no T04 + eventos de memória dos demais talhões."""
    t04 = fields[3]
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
        farm_id=farm.id, field_id=t04.id, title="Vistoria — setor sudoeste do pivô (T04)", kind="vistoria",
        priority="alta", assignee="Carlos Menezes (técnico de campo)", due_date=d(a["peak"] + 1),
        instructions="Percorrer o setor sudoeste do pivô. Verificar sintomas de déficit hídrico (murcha nas horas "
                     "quentes), batida de pano para percevejos e lagartas, e funcionamento dos emissores das "
                     "últimas torres.",
        status="verificada", geom=sector_wkt,
    )
    s.add(task)
    s.flush()
    insp = Inspection(
        task_id=task.id, inspected_at=d(a["peak"] + 2), recorded_by="Carlos Menezes",
        verified_cause="Deficiência hídrica",
        findings="Plantas com murcha nas horas quentes e folíolos virados no setor sudoeste. Emissores entupidos "
                 "nas duas últimas torres do pivô. Batida de pano abaixo do nível de ação para percevejos.",
        notes="Solo de textura mais arenosa nesse setor. Recomendado revisar emissores e lâmina aplicada.",
        photos=[],
    )
    s.add(insp)
    s.flush()
    interv = Intervention(
        field_id=t04.id, inspection_id=insp.id,
        recommended_action="Revisar emissores das torres finais e ajustar lâmina de irrigação no setor afetado.",
        approved_action="Limpeza/troca de emissores das torres 7 e 8 e aumento da lâmina para 8 mm/dia no "
                        "setor sudoeste durante 10 dias.",
        approved_by="Eng. Agr. Mariana Rocha (CREA-MT)", executed_at=d(a["intervention_das"]),
        actual_cost=round(affected_ha * 92.0, 2),
        notes="Custos incluem mão de obra, peças e energia adicional estimada. (Dados de demonstração)",
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
        method="Diferença-em-diferenças simples: variação do NDVI médio do setor afetado entre as janelas antes "
               "e depois, descontada a variação no restante do pivô (área de comparação) no mesmo período. "
               "Observações com nuvem descartadas.",
        comparison_area="Restante do T04 (mesmo pivô, mesma cultivar e data de semeadura), fora do setor sudoeste.",
        limitations="Houve retorno das chuvas no mesmo período, o que também contribui para a recuperação. "
                    "Apenas um evento; sem parcela-controle sem intervenção. Indica associação, não prova causal.",
        confidence="moderada",
    )
    s.add(outcome)

    ev = lambda f, season, date_, typ, title, summary, refs=None: MemoryEvent(
        field_id=f.id, season_id=season.id, date=date_, type=typ, title=title, summary=summary, refs=refs or {},
    )
    s.add_all([
        ev(t04, prev, prev.sowing_date, "safra", "Semeadura safra 2024/25", "Soja semeada no pivô central."),
        ev(t04, prev, d(a["onset"] + 8), "anomalia", "Queda de NDVI no setor sudoeste do pivô",
           f"NDVI abaixo do histórico da própria área e da mediana do talhão em ~{br(affected_ha, 0)} ha, "
           "após 12 dias sem chuva.", {"area_ha": affected_ha}),
        ev(t04, prev, insp.inspected_at, "vistoria", "Vistoria confirmou deficiência hídrica",
           insp.findings, {"task_id": task.id, "inspection_id": insp.id}),
        ev(t04, prev, interv.executed_at, "intervencao", "Ajuste de emissores e lâmina do pivô",
           f"{interv.approved_action} Custo realizado: R$ {br(interv.actual_cost, 2)}.",
           {"intervention_id": interv.id}),
        ev(t04, prev, d(at), "resultado", "NDVI do setor recuperou parcialmente",
           f"NDVI do setor: {br(b, 2)} → {br(af_v, 2)}; área de comparação: {br(cb, 2)} → {br(ca, 2)}. "
           f"Diferença líquida {"+" if outcome.delta_vs_comparison >= 0 else "−"}{br(abs(outcome.delta_vs_comparison), 2)}. Chuvas também retornaram no período — "
           "associação, não prova causal.", {"intervention_id": interv.id}),
        ev(t04, prev, prev.harvest_date, "safra", "Colheita safra 2024/25",
           f"Produtividade média do talhão: {br(prev.realized_yield_sc_ha, 1)} sc/ha (esperado {br(prev.expected_yield_sc_ha, 0)})."),
    ])
    for f in fields:
        for season in seasons:
            if f is t04 and season is prev:
                continue
            s.add(ev(f, season, season.sowing_date, "safra", f"Semeadura safra {season.name}",
                     f"Soja semeada em {f.name}."))
    s.add(ev(fields[2], seasons[2], seasons[2].sowing_date + timedelta(days=21), "nota",
             "Estande irregular observado na emergência",
             "Operador relatou falhas de plantio em faixa diagonal do talhão (possível problema na semeadora)."))


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
