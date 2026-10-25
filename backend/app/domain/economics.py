"""Modelo econômico transparente — funções puras.

Exposição estimada ≠ perda confirmada ≠ economia realizada. Tudo aqui é *estimativa* com premissas explícitas.
"""
from dataclasses import asdict, dataclass

CONFIDENCE_WEIGHT = {"alta": 1.0, "moderada": 0.7, "baixa": 0.4}
YELLOW_WEIGHT = 0.5  # célula em atenção conta como meia área afetada


@dataclass(frozen=True)
class EconomicAssumptions:
    produtividade_esperada_sc_ha: float = 62.0
    preco_saca_rs: float = 120.0
    perda_min_pct: float = 8.0
    perda_max_pct: float = 25.0
    custo_vistoria_rs: float = 450.0
    custo_intervencao_rs_ha: float = 85.0

    @classmethod
    def from_dict(cls, d: dict | None) -> "EconomicAssumptions":
        d = d or {}
        return cls(**{k: float(d[k]) for k in cls.__dataclass_fields__ if k in d})


@dataclass(frozen=True)
class Exposure:
    affected_ha: float
    gross_value_rs: float
    exposure_min: float
    exposure_max: float
    inspection_cost: float
    intervention_cost: float
    formula: str
    assumptions: dict


def affected_area(red_ha: float, yellow_ha: float) -> float:
    return red_ha + YELLOW_WEIGHT * yellow_ha


def estimate_exposure(red_ha: float, yellow_ha: float, a: EconomicAssumptions) -> Exposure:
    ha = affected_area(red_ha, yellow_ha)
    gross = ha * a.produtividade_esperada_sc_ha * a.preco_saca_rs
    return Exposure(
        affected_ha=round(ha, 1),
        gross_value_rs=round(gross, 2),
        exposure_min=round(gross * a.perda_min_pct / 100, 2),
        exposure_max=round(gross * a.perda_max_pct / 100, 2),
        inspection_cost=round(a.custo_vistoria_rs, 2),
        intervention_cost=round(ha * a.custo_intervencao_rs_ha, 2),
        formula="área afetada (ha) × produtividade esperada (sc/ha) × preço (R$/sc) × faixa de perda (%). "
                f"Área afetada = área crítica + {YELLOW_WEIGHT:.0%} da área em atenção.",
        assumptions={**asdict(a), "peso_area_atencao": YELLOW_WEIGHT, "area_critica_ha": round(red_ha, 1),
                     "area_atencao_ha": round(yellow_ha, 1)},
    )


# ------------------------------------------------------------------ urgência e prioridade
def soybean_stage(das: int) -> str:
    """Estádio fenológico aproximado da soja por DAS (ciclo ~120 dias). Indicativo."""
    for limit, stage in ((10, "VE"), (45, "Vegetativo (V)"), (55, "R1–R2 (florescimento)"),
                         (70, "R3–R4 (formação de vagens)"), (85, "R5 (enchimento de grãos)"),
                         (100, "R6 (grão cheio)"), (112, "R7 (maturação fisiológica)")):
        if das < limit:
            return stage
    return "R8 (maturação plena)"


def urgency(das: int, worsening: bool) -> tuple[float, str]:
    """0–1. Maior no período reprodutivo (R3–R6), quando estresse reduz mais a produtividade."""
    if 55 <= das < 100:
        base, why = 1.0, "período reprodutivo — alta sensibilidade a estresse"
    elif 40 <= das < 55 or 100 <= das < 112:
        base, why = 0.7, "estádio de sensibilidade intermediária"
    else:
        base, why = 0.4, "estádio de menor sensibilidade"
    if worsening:
        base = min(1.0, base + 0.15)
        why += "; área em anomalia crescendo nas últimas observações"
    return round(base, 2), why


def priority_score(exposure_mid: float, urgency_value: float, confidence: str) -> float:
    return round(exposure_mid * urgency_value * CONFIDENCE_WEIGHT[confidence], 2)


PRIORITY_FORMULA = ("prioridade = exposição média estimada (R$) × urgência (0–1, pelo estádio e tendência) × "
                    "peso da confiança (alta 1,0 · moderada 0,7 · baixa 0,4)")
