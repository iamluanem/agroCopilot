"""Transparent economic model — pure functions.

Estimated exposure ≠ confirmed loss ≠ realized savings. Everything here is an *estimate* with explicit assumptions.
Yield is expressed in 60 kg bags per hectare (the Brazilian market standard) and prices in BRL (R$).
"""
from dataclasses import asdict, dataclass

CONFIDENCE_WEIGHT = {"high": 1.0, "moderate": 0.7, "low": 0.4}
YELLOW_WEIGHT = 0.5  # a "watch" cell counts as half an affected area


@dataclass(frozen=True)
class EconomicAssumptions:
    expected_yield_bags_ha: float = 62.0
    bag_price_brl: float = 120.0
    loss_min_pct: float = 8.0
    loss_max_pct: float = 25.0
    inspection_cost_brl: float = 450.0
    intervention_cost_brl_ha: float = 85.0

    @classmethod
    def from_dict(cls, d: dict | None) -> "EconomicAssumptions":
        d = d or {}
        return cls(**{k: float(d[k]) for k in cls.__dataclass_fields__ if k in d})


@dataclass(frozen=True)
class Exposure:
    affected_ha: float
    gross_value_brl: float
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
    gross = ha * a.expected_yield_bags_ha * a.bag_price_brl
    return Exposure(
        affected_ha=round(ha, 1),
        gross_value_brl=round(gross, 2),
        exposure_min=round(gross * a.loss_min_pct / 100, 2),
        exposure_max=round(gross * a.loss_max_pct / 100, 2),
        inspection_cost=round(a.inspection_cost_brl, 2),
        intervention_cost=round(ha * a.intervention_cost_brl_ha, 2),
        formula="affected area (ha) × expected yield (bags/ha) × price (R$/bag) × loss range (%). "
                f"Affected area = critical area + {YELLOW_WEIGHT:.0%} of the watch area.",
        assumptions={**asdict(a), "watch_area_weight": YELLOW_WEIGHT, "critical_area_ha": round(red_ha, 1),
                     "watch_area_ha": round(yellow_ha, 1)},
    )


# ------------------------------------------------------------------ urgency and priority
def soybean_stage(das: int) -> str:
    """Approximate soybean growth stage by days after sowing (~120-day cycle). Indicative only."""
    for limit, stage in ((10, "VE"), (45, "Vegetative (V)"), (55, "R1–R2 (flowering)"),
                         (70, "R3–R4 (pod set)"), (85, "R5 (seed fill)"),
                         (100, "R6 (full seed)"), (112, "R7 (physiological maturity)")):
        if das < limit:
            return stage
    return "R8 (full maturity)"


def urgency(das: int, worsening: bool) -> tuple[float, str]:
    """0–1. Highest in the reproductive period (R3–R6), when stress costs the most yield."""
    if 55 <= das < 100:
        base, why = 1.0, "reproductive period — high sensitivity to stress"
    elif 40 <= das < 55 or 100 <= das < 112:
        base, why = 0.7, "intermediate-sensitivity stage"
    else:
        base, why = 0.4, "low-sensitivity stage"
    if worsening:
        base = min(1.0, base + 0.15)
        why += "; anomaly area growing in the latest scenes"
    return round(base, 2), why


def priority_score(exposure_mid: float, urgency_value: float, confidence: str) -> float:
    return round(exposure_mid * urgency_value * CONFIDENCE_WEIGHT[confidence], 2)


PRIORITY_FORMULA = ("priority = mid estimated exposure (R$) × urgency (0–1, by crop stage and trend) × "
                    "confidence weight (high 1.0 · moderate 0.7 · low 0.4)")
