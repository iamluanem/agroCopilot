"""Motor de risco por célula — funções puras (sem I/O).

Ideia: o índice de vegetação é um *sinal* que direciona vistoria, não um diagnóstico.
A anomalia combina duas referências:
  (a) histórico da própria célula no mesmo estádio (DAS) de safras anteriores,
      descontada a variação geral da fazenda na safra atual;
  (b) mediana do talhão na mesma data.
"""
from dataclasses import dataclass

import numpy as np

LEVELS = ("verde", "amarelo", "vermelho", "sem_dado")
LEVEL_CODE = {name: i for i, name in enumerate(LEVELS)}
CONFIDENCE = ("baixa", "moderada", "alta")

MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class RiskThresholds:
    yellow: float = 1.5
    red: float = 2.5
    sigma_floor: float = 0.025
    weight_hist: float = 0.6


@dataclass(frozen=True)
class CellRisk:
    score: np.ndarray        # positivo = pior que o esperado
    level: np.ndarray        # índice em LEVELS
    confidence: np.ndarray   # índice em CONFIDENCE (-1 quando sem dado)
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
    """Calcula score, nível e confiança por célula.

    ndvi        NDVI atual por célula
    baseline    média histórica da célula no mesmo DAS (NaN se inexistente)
    field_idx   índice do talhão de cada célula
    cloud       True quando a observação está contaminada por nuvem
    recent_valid nº de observações válidas da célula nas últimas 3 datas (0–3)
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

    level = np.full(n, LEVEL_CODE["sem_dado"], dtype=np.int8)
    ok = valid & np.isfinite(score)
    level[ok] = LEVEL_CODE["verde"]
    level[ok & (score >= t.yellow)] = LEVEL_CODE["amarelo"]
    level[ok & (score >= t.red)] = LEVEL_CODE["vermelho"]

    # Confiança: concordância entre as duas referências + densidade de observações válidas
    agree = has_hist & np.isfinite(z_field) & (np.sign(z_hist) == np.sign(z_field))
    pts = agree.astype(int) + has_hist.astype(int) + (recent_valid >= 3).astype(int)
    confidence = np.where(pts >= 3, 2, np.where(pts >= 2, 1, 0)).astype(np.int8)
    confidence[~ok] = -1

    return CellRisk(score=score, level=level, confidence=confidence, z_hist=z_hist, z_field=z_field)


def field_level(area_by_level: dict[str, float]) -> str:
    """Classifica o talhão a partir da área (ha) em cada nível."""
    if area_by_level.get("vermelho", 0) >= 10:
        return "vermelho"
    if area_by_level.get("vermelho", 0) + area_by_level.get("amarelo", 0) >= 15:
        return "amarelo"
    return "verde"
