"""Rule-based agronomic hypotheses — pure functions.

Principle: a satellite index is a signal, not a diagnosis. Every hypothesis lists its evidence and the missing data.
Without a field inspection, no hypothesis goes above "moderate" confidence.
"""
from dataclasses import dataclass, field

import numpy as np

from app.core.fmt import num

CAUSES = {
    "water_stress": "Water stress",
    "pest_disease": "Pest or disease pressure",
    "nutrient_deficiency": "Nutrient deficiency",
    "stand_failure": "Stand failure / uneven emergence",
}
FIELD_CHECK_CAP = "moderate"


@dataclass(frozen=True)
class ZoneContext:
    red_ha: float
    yellow_ha: float
    das: int
    stage: str
    pattern: str                    # contiguous_sector | linear_strip | scattered_patches
    onset_das: int | None           # first date of the season on which the zone was already anomalous
    ndvi_drop: float                # zone mean NDVI − history (negative = worse)
    max_dry_days: int               # longest run without rain (< 2 mm) in the previous 30 days
    rain_21d_mm: float
    tmax_dry_mean: float | None
    soil_texture: str | None
    irrigation: str
    recurrence_share: float         # share of the zone that was anomalous last season at a similar stage
    dry_start_das: int | None = None  # DAS at which the longest recent dry run started
    prior_verified: list[tuple[str, str]] = field(default_factory=list)  # (season, verified cause)
    field_notes: list[str] = field(default_factory=list)  # field notes recorded this season


@dataclass
class Hypothesis:
    key: str
    cause: str
    score: float
    confidence: str
    evidence: list[str]
    missing: list[str]


def classify_pattern(rows: np.ndarray, cols: np.ndarray) -> tuple[str, float]:
    """Spatial pattern of the anomalous cells: returns (pattern, share in the largest cluster)."""
    if rows.size < 4:
        return "scattered_patches", 0.0
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
        return "linear_strip", share
    if share < 0.45:
        return "scattered_patches", share
    return ("linear_strip" if _elongation(np.array(largest)) > 6 else "contiguous_sector"), share


def _elongation(pts: np.ndarray) -> float:
    ev = np.sort(np.linalg.eigvalsh(np.cov(pts.astype(float).T)))
    return float(ev[1] / max(ev[0], 1e-6))


PATTERN_LABEL = {
    "contiguous_sector": "contiguous sector",
    "linear_strip": "linear strip",
    "scattered_patches": "scattered patches",
}


def _conf(score: float) -> str:
    return FIELD_CHECK_CAP if score >= 0.5 else "low"


def rank_hypotheses(z: ZoneContext) -> list[Hypothesis]:
    soil = (z.soil_texture or "").lower()
    sandy = "sand" in soil or "medium" in soil
    reproductive = 55 <= z.das < 112
    early_onset = z.onset_das is not None and z.onset_das <= 45
    before_dry = (z.onset_das is not None and z.dry_start_das is not None and z.onset_das < z.dry_start_das - 5)
    stand_notes = [n for n in z.field_notes if any(k in n.lower() for k in ("stand", "skip", "planter", "seeding"))]
    verified = {c.lower() for _, c in z.prior_verified}
    out: list[Hypothesis] = []

    # ---- water stress
    s, ev = 0.1, []
    if z.max_dry_days >= 10:
        s += 0.3 if not before_dry else 0.1
        ev.append(f"{z.max_dry_days} consecutive days without rain in the previous 30 days"
                  + (f" (mean max {num(z.tmax_dry_mean, 1)} °C)" if z.tmax_dry_mean else ""))
    elif z.max_dry_days >= 7:
        s += 0.15
        ev.append(f"{z.max_dry_days} consecutive days without rain in the previous 30 days")
    if sandy:
        s += 0.15
        ev.append(f"Soil with lower water-holding capacity: {z.soil_texture}")
    if any("water" in c for c in verified):
        s += 0.25
        season = next(sn for sn, c in z.prior_verified if "water" in c.lower())
        ev.append(f"An inspection confirmed water stress in this area in the {season} season")
    if z.pattern == "contiguous_sector":
        s += 0.05
        ev.append("Anomaly concentrated in a contiguous sector")
    if not early_onset and z.onset_das is not None and not before_dry:
        s += 0.05
        ev.append(f"Decline started late in the cycle (DAS {z.onset_das}), after the dry spell began")
    if before_dry:
        s -= 0.2
        ev.append(f"Against: the anomaly already existed before the dry spell (DAS {z.onset_das})")
    missing = ["Field inspection (midday wilting, soil moisture)"]
    if "pivot" in z.irrigation:
        missing.append("Applied irrigation depth and a check of the pivot sprinklers")
    out.append(Hypothesis("water_stress", CAUSES["water_stress"], s, _conf(s), ev, missing))

    # ---- pests / disease
    s, ev = 0.15, []
    if z.pattern == "scattered_patches":
        s += 0.2
        ev.append("Scattered-patch pattern, consistent with infestation hotspots")
    if reproductive:
        s += 0.05
        ev.append(f"Stage {z.stage}: peak pressure period for stink bugs and foliar diseases")
    if z.max_dry_days < 7:
        s += 0.1
        ev.append("No meaningful dry spell that would explain the decline")
    out.append(Hypothesis("pest_disease", CAUSES["pest_disease"], s, _conf(s), ev,
                          ["Beat-sheet sampling with counts per sampling point",
                           "Leaf inspection (lesions, defoliation) with geotagged photos"]))

    # ---- nutrient
    s, ev = 0.12, []
    if z.recurrence_share >= 0.4 and not verified:
        s += 0.15
        ev.append("Same area showed low vigor last season with no verified cause")
    if z.pattern != "scattered_patches" and not early_onset and z.max_dry_days < 7:
        s += 0.1
        ev.append("Gradual, spatially coherent decline without apparent weather stress")
    out.append(Hypothesis("nutrient_deficiency", CAUSES["nutrient_deficiency"], s, _conf(s), ev,
                          ["Leaf tissue analysis", "Soil analysis of the zone vs. a reference area"]))

    # ---- stand failure
    s, ev = 0.05, []
    if early_onset:
        s += 0.45
        ev.append(f"Anomaly present since the vegetative stage (DAS {z.onset_das})")
    if stand_notes:
        s += 0.15
        ev.append(f"Field record: {stand_notes[0]}")
    if z.pattern == "linear_strip":
        s += 0.25
        ev.append("Linear-strip pattern, typical of a planter failure or a machinery pass")
    out.append(Hypothesis("stand_failure", CAUSES["stand_failure"], s, _conf(s), ev,
                          ["Plants per meter inside vs. outside the strip",
                           "Planting operation record (calibration, speed)"]))

    out.sort(key=lambda h: h.score, reverse=True)
    return out


def recommended_next_step(top: Hypothesis, red_ha: float) -> str:
    base = "Run a targeted inspection of the affected zone before deciding on any intervention"
    detail = {
        "water_stress": "checking soil moisture, wilting symptoms and the irrigation system.",
        "pest_disease": "with beat-sheet sampling and geotagged leaf inspection.",
        "nutrient_deficiency": "collecting leaf and soil samples inside and outside the zone.",
        "stand_failure": "counting plants per meter inside and outside the strip.",
    }[top.key]
    urgency = " High priority given the size of the critical area." if red_ha >= 10 else ""
    return f"{base}, {detail}{urgency}"
