"""Per-cell risk engine — pure functions (no I/O).

Principle: a vegetation index is a *signal* that directs scouting, not a diagnosis.
The anomaly combines two references:
  (a) the cell's own history at the same crop stage (days after sowing) in previous seasons,
      net of the farm-wide shift in the current season;
  (b) the field median on the same date.
"""
from dataclasses import dataclass

import numpy as np

LEVELS = ("green", "yellow", "red", "no_data")
LEVEL_CODE = {name: i for i, name in enumerate(LEVELS)}
CONFIDENCE = ("low", "moderate", "high")

MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class RiskThresholds:
    yellow: float = 1.5
    red: float = 2.5
    sigma_floor: float = 0.025
    weight_hist: float = 0.6


@dataclass(frozen=True)
class CellRisk:
    score: np.ndarray        # positive = worse than expected
    level: np.ndarray        # index into LEVELS
    confidence: np.ndarray   # index into CONFIDENCE (-1 when no data)
    z_hist: np.ndarray
    z_field: np.ndarray


def _robust_sigma(values: np.ndarray, floor: float) -> float:
    v = values[np.isfinite(values)]
    if v.size < 5:
        return floor
    mad = np.median(np.abs(v - np.median(v)))
    return max(floor, MAD_TO_SIGMA * mad)


def compute_cell_risk(
    ndvi: np.ndarray,
    baseline: np.ndarray,
    field_idx: np.ndarray,
    cloud: np.ndarray,
    recent_valid: np.ndarray,
    t: RiskThresholds = RiskThresholds(),
) -> CellRisk:
    """Compute score, level and confidence per cell.

    ndvi         current NDVI per cell
    baseline     the cell's historical mean at the same DAS (NaN if none)
    field_idx    field index of each cell
    cloud        True when the observation is cloud-contaminated
    recent_valid number of valid observations of the cell in the last 3 dates (0–3)
    """
    n = ndvi.size
    valid = ~cloud & np.isfinite(ndvi)

    diff = np.where(valid, ndvi - baseline, np.nan)
    farm_shift = np.nanmedian(diff) if np.isfinite(diff).any() else 0.0
    sigma_hist = _robust_sigma(diff, t.sigma_floor)
    z_hist = (diff - farm_shift) / sigma_hist

    z_field = np.full(n, np.nan)
    for f in np.unique(field_idx):
        m = (field_idx == f) & valid
        if m.sum() < 5:
            continue
        vals = ndvi[m]
        z_field[m] = (vals - np.median(vals)) / _robust_sigma(vals, t.sigma_floor)

    has_hist = np.isfinite(z_hist)
    combined = np.where(
        has_hist,
        t.weight_hist * z_hist + (1 - t.weight_hist) * np.nan_to_num(z_field),
        z_field,
    )
    score = -combined

    level = np.full(n, LEVEL_CODE["no_data"], dtype=np.int8)
    ok = valid & np.isfinite(score)
    level[ok] = LEVEL_CODE["green"]
    level[ok & (score >= t.yellow)] = LEVEL_CODE["yellow"]
    level[ok & (score >= t.red)] = LEVEL_CODE["red"]

    # Confidence: agreement between both references + density of valid observations
    agree = has_hist & np.isfinite(z_field) & (np.sign(z_hist) == np.sign(z_field))
    pts = agree.astype(int) + has_hist.astype(int) + (recent_valid >= 3).astype(int)
    confidence = np.where(pts >= 3, 2, np.where(pts >= 2, 1, 0)).astype(np.int8)
    confidence[~ok] = -1

    return CellRisk(score=score, level=level, confidence=confidence, z_hist=z_hist, z_field=z_field)


def field_level(area_by_level: dict[str, float]) -> str:
    """Classify a field from the area (ha) at each level."""
    if area_by_level.get("red", 0) >= 10:
        return "red"
    if area_by_level.get("red", 0) + area_by_level.get("yellow", 0) >= 15:
        return "yellow"
    return "green"
