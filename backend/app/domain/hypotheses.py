"""Hipóteses agronômicas baseadas em regras — funções puras.

Princípio: índice de satélite é sinal, não diagnóstico. Toda hipótese lista evidências e o dado que falta.
Sem vistoria de campo, nenhuma hipótese passa de confiança "moderada".
"""
from dataclasses import dataclass, field

import numpy as np

from app.core.fmt import br

CAUSES = {
    "deficiencia_hidrica": "Deficiência hídrica",
    "pragas_doencas": "Pressão de pragas ou doenças",
    "deficiencia_nutricional": "Deficiência nutricional",
    "falha_estande": "Falha de estande / emergência desuniforme",
}
FIELD_CHECK_CAP = "moderada"


@dataclass(frozen=True)
class ZoneContext:
    red_ha: float
    yellow_ha: float
    das: int
    stage: str
    pattern: str                    # setor_contiguo | faixa_linear | manchas_dispersas
    onset_das: int | None           # 1ª data da safra em que a zona já aparecia anômala
    ndvi_drop: float                # NDVI médio da zona − histórico (negativo = pior)
    max_dry_days: int               # maior sequência sem chuva (< 2 mm) nos 30 dias anteriores
    rain_21d_mm: float
    tmax_dry_mean: float | None
    soil_texture: str | None
    irrigation: str
    recurrence_share: float         # fração da zona que já foi anômala na safra anterior em estádio similar
    dry_start_das: int | None = None  # DAS em que começou a maior sequência seca recente
    prior_verified: list[tuple[str, str]] = field(default_factory=list)  # (safra, causa verificada)
    field_notes: list[str] = field(default_factory=list)  # notas de campo registradas na safra


@dataclass
class Hypothesis:
    key: str
    cause: str
    score: float
    confidence: str
    evidence: list[str]
    missing: list[str]


def classify_pattern(rows: np.ndarray, cols: np.ndarray) -> tuple[str, float]:
    """Padrão espacial das células anômalas: retorna (padrão, fração no maior agrupamento)."""
    if rows.size < 4:
        return "manchas_dispersas", 0.0
    cells = set(zip(rows.tolist(), cols.tolist()))
    seen, largest = set(), []
    for c in cells:
        if c in seen:
            continue
        comp, stack = [], [c]
        seen.add(c)
        while stack:
            r, k = stack.pop()
            comp.append((r, k))
            for dr in (-1, 0, 1):
                for dk in (-1, 0, 1):
                    n = (r + dr, k + dk)
                    if n in cells and n not in seen:
                        seen.add(n)
                        stack.append(n)
        if len(comp) > len(largest):
            largest = comp
    share = len(largest) / len(cells)
    if _elongation(np.column_stack([rows, cols])) > 6:
        return "faixa_linear", share
    if share < 0.45:
        return "manchas_dispersas", share
    return ("faixa_linear" if _elongation(np.array(largest)) > 6 else "setor_contiguo"), share


def _elongation(pts: np.ndarray) -> float:
    ev = np.sort(np.linalg.eigvalsh(np.cov(pts.astype(float).T)))
    return float(ev[1] / max(ev[0], 1e-6))


PATTERN_LABEL = {
    "setor_contiguo": "setor contíguo",
    "faixa_linear": "faixa linear",
    "manchas_dispersas": "manchas dispersas",
}


def _conf(score: float) -> str:
    return FIELD_CHECK_CAP if score >= 0.5 else "baixa"


def rank_hypotheses(z: ZoneContext) -> list[Hypothesis]:
    soil = (z.soil_texture or "").lower()
    sandy = "arenos" in soil or "média" in soil or "media" in soil
    reproductive = 55 <= z.das < 112
    early_onset = z.onset_das is not None and z.onset_das <= 45
    before_dry = (z.onset_das is not None and z.dry_start_das is not None and z.onset_das < z.dry_start_das - 5)
    stand_notes = [n for n in z.field_notes if any(k in n.lower() for k in ("estande", "falha", "semead"))]
    verified = {c.lower() for _, c in z.prior_verified}
    out: list[Hypothesis] = []

    # ---- deficiência hídrica
    s, ev = 0.1, []
    if z.max_dry_days >= 10:
        s += 0.3 if not before_dry else 0.1
        ev.append(f"{z.max_dry_days} dias consecutivos sem chuva nos 30 dias anteriores"
                  + (f" (máx. média {br(z.tmax_dry_mean, 1)} °C)" if z.tmax_dry_mean else ""))
    elif z.max_dry_days >= 7:
        s += 0.15
        ev.append(f"{z.max_dry_days} dias consecutivos sem chuva nos 30 dias anteriores")
    if sandy:
        s += 0.15
        ev.append(f"Solo com menor retenção de água: {z.soil_texture}")
    if any("hídric" in c or "hidric" in c for c in verified):
        s += 0.25
        safra = next(sf for sf, c in z.prior_verified if "hídric" in c.lower() or "hidric" in c.lower())
        ev.append(f"Vistoria confirmou deficiência hídrica nesta área na safra {safra}")
    if z.pattern == "setor_contiguo":
        s += 0.05
        ev.append("Anomalia concentrada em setor contíguo")
    if not early_onset and z.onset_das is not None and not before_dry:
        s += 0.05
        ev.append(f"Queda começou tarde no ciclo (DAS {z.onset_das}), após o início do período seco")
    if before_dry:
        s -= 0.2
        ev.append(f"Contra: anomalia já existia antes do período seco (DAS {z.onset_das})")
    missing = ["Vistoria de campo (murcha nas horas quentes, umidade do solo)"]
    if "pivô" in z.irrigation or "pivo" in z.irrigation:
        missing.append("Registro de lâmina aplicada e checagem dos emissores do pivô")
    out.append(Hypothesis("deficiencia_hidrica", CAUSES["deficiencia_hidrica"], s, _conf(s), ev, missing))

    # ---- pragas / doenças
    s, ev = 0.15, []
    if z.pattern == "manchas_dispersas":
        s += 0.2
        ev.append("Padrão em manchas dispersas, compatível com focos")
    if reproductive:
        s += 0.05
        ev.append(f"Estádio {z.stage}, período de maior pressão de percevejos e doenças foliares")
    if z.max_dry_days < 7:
        s += 0.1
        ev.append("Sem veranico relevante que explique a queda")
    out.append(Hypothesis("pragas_doencas", CAUSES["pragas_doencas"], s, _conf(s), ev,
                          ["Batida de pano e contagem por ponto amostral",
                           "Inspeção de folhas (lesões, desfolha) com foto georreferenciada"]))

    # ---- nutricional
    s, ev = 0.12, []
    if z.recurrence_share >= 0.4 and not verified:
        s += 0.15
        ev.append("Mesma área apresentou baixo vigor na safra anterior sem causa verificada")
    if z.pattern != "manchas_dispersas" and not early_onset and z.max_dry_days < 7:
        s += 0.1
        ev.append("Queda gradual e espacialmente coerente sem estresse climático aparente")
    out.append(Hypothesis("deficiencia_nutricional", CAUSES["deficiencia_nutricional"], s, _conf(s), ev,
                          ["Análise foliar", "Análise de solo da zona vs. área de referência"]))

    # ---- falha de estande
    s, ev = 0.05, []
    if early_onset:
        s += 0.45
        ev.append(f"Anomalia presente desde a fase vegetativa (DAS {z.onset_das})")
    if stand_notes:
        s += 0.15
        ev.append(f"Registro de campo: {stand_notes[0]}")
    if z.pattern == "faixa_linear":
        s += 0.25
        ev.append("Padrão em faixa linear, típico de falha de semeadora ou passada de máquina")
    out.append(Hypothesis("falha_estande", CAUSES["falha_estande"], s, _conf(s), ev,
                          ["Contagem de plantas por metro na faixa vs. fora dela",
                           "Registro da operação de semeadura (regulagem, velocidade)"]))

    out.sort(key=lambda h: h.score, reverse=True)
    return out


def recommended_next_step(top: Hypothesis, red_ha: float) -> str:
    base = "Realizar vistoria direcionada na zona afetada antes de decidir qualquer intervenção"
    detail = {
        "deficiencia_hidrica": "verificando umidade do solo, sintomas de murcha e funcionamento da irrigação.",
        "pragas_doencas": "com batida de pano e inspeção foliar georreferenciada.",
        "deficiencia_nutricional": "coletando amostras foliar e de solo dentro e fora da zona.",
        "falha_estande": "contando plantas por metro dentro e fora da faixa.",
    }[top.key]
    urgency = " Prioridade alta pelo tamanho da área crítica." if red_ha >= 10 else ""
    return f"{base}, {detail}{urgency}"
