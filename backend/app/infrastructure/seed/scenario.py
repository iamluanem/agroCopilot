"""Cenário de demonstração determinístico — Fazenda Santa Aurora (Sorriso-MT).

Tudo aqui é SINTÉTICO: limites dos talhões, NDVI/NDRE, clima e histórico operacional.
Nenhum valor representa medição real de satélite ou operação real de campo.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from pyproj import Transformer
from shapely import affinity, box, intersection, Point, Polygon
from shapely.ops import transform as shp_transform

ORIGIN_LONLAT = (-55.872, -12.612)  # canto SO da fazenda (sintético), oeste de Sorriso-MT
UTM = "EPSG:32721"
RNG_SEED = 20251006

_to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
_to_wgs = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
OX, OY = _to_utm.transform(*ORIGIN_LONLAT)


@dataclass(frozen=True)
class SeasonSpec:
    name: str
    sowing: date
    harvest: date | None
    last_das: int
    offset: float               # efeito geral da safra no NDVI
    cloud_das: tuple[int, ...]
    expected_yield: float
    realized_yield: float | None
    is_current: bool = False


SEASONS = (
    SeasonSpec("2023/24", date(2023, 10, 4), date(2024, 2, 5), 120, -0.020, (40, 75), 60.0, 55.4),
    SeasonSpec("2024/25", date(2024, 10, 7), date(2025, 2, 8), 120, 0.010, (25, 60, 100), 62.0, 61.1),
    SeasonSpec("2025/26", date(2025, 10, 6), None, 95, 0.000, (30, 55, 80), 62.0, None, True),
)
OBS_STEP_DAYS = 5
FIRST_DAS = 10

# Anomalia no setor sudoeste do pivô (T04)
PIVOT_CENTER = (900.0, 760.0)
PIVOT_RADIUS = 700.0
PREV_ANOMALY = dict(onset=62, peak=75, intervention_das=81, depth=0.16, residual=0.35)
CURR_ANOMALY = dict(onset=80, peak=95, depth=0.24)


def das_dates(season: SeasonSpec) -> list[tuple[int, date]]:
    return [(d, season.sowing + timedelta(days=d)) for d in range(FIRST_DAS, season.last_das + 1, OBS_STEP_DAYS)]


# ---------------------------------------------------------------- geometria (metros, UTM local)
def _field_shapes() -> list[dict]:
    t01 = Polygon([(0, 1600), (1700, 1600), (1700, 3140), (380, 3140), (0, 2780)])
    t02 = box(1730, 1600, 3430, 3140)
    t03 = Polygon([(3460, 1600), (5080, 1600), (5240, 3140), (3460, 3140)])
    t04 = Point(PIVOT_CENTER).buffer(PIVOT_RADIUS, quad_segs=32)
    t05 = Polygon([(1730, 0), (3430, 0), (3430, 1570), (2050, 1570), (2050, 1330), (1730, 1330)])
    return [
        dict(code="T01", geom=t01, soil="Latossolo Vermelho-Amarelo argiloso", irrigation="sequeiro"),
        dict(code="T02", geom=t02, soil="Latossolo Vermelho-Amarelo argiloso", irrigation="sequeiro"),
        dict(code="T03", geom=t03, soil="Latossolo Vermelho-Amarelo médio", irrigation="sequeiro"),
        dict(code="T04", geom=t04, soil="Latossolo textura média a arenosa (setor SO)", irrigation="pivô central"),
        dict(code="T05", geom=t05, soil="Latossolo Vermelho-Amarelo argiloso", irrigation="sequeiro"),
    ]


def to_wgs(geom):
    return shp_transform(lambda x, y, z=None: _to_wgs.transform(np.asarray(x) + OX, np.asarray(y) + OY), geom)


@dataclass
class CellGrid:
    field_idx: np.ndarray
    row: np.ndarray
    col: np.ndarray
    cx: np.ndarray
    cy: np.ndarray
    area_ha: np.ndarray
    geoms: list = field(default_factory=list)  # shapely em metros locais


def build_grid(fields: list[dict], cell_m: int) -> CellGrid:
    fi, rows, cols, cxs, cys, areas, geoms = [], [], [], [], [], [], []
    full = cell_m * cell_m
    for idx, f in enumerate(fields):
        g = f["geom"]
        minx, miny, maxx, maxy = g.bounds
        c0, c1 = int(minx // cell_m), int(np.ceil(maxx / cell_m))
        r0, r1 = int(miny // cell_m), int(np.ceil(maxy / cell_m))
        cc, rr = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
        cc, rr = cc.ravel(), rr.ravel()
        boxes = box(cc * cell_m, rr * cell_m, (cc + 1) * cell_m, (rr + 1) * cell_m)
        clipped = intersection(boxes, g)
        a = np.array([c.area for c in clipped])
        keep = a >= 0.3 * full
        for c, r, geom, area in zip(cc[keep], rr[keep], clipped[keep], a[keep]):
            if geom.geom_type != "Polygon":
                geom = max(geom.geoms, key=lambda p: p.area) if hasattr(geom, "geoms") else geom
            ct = geom.centroid
            fi.append(idx); rows.append(r); cols.append(c)
            cxs.append(ct.x); cys.append(ct.y); areas.append(area / 10_000); geoms.append(geom)
    return CellGrid(np.array(fi), np.array(rows), np.array(cols), np.array(cxs), np.array(cys), np.array(areas), geoms)


# ---------------------------------------------------------------- campos espaciais suaves
def _smooth_field(rng: np.random.Generator, x, y, n=7, amp=0.012, wl=(250, 900)):
    out = np.zeros_like(x, dtype=float)
    for _ in range(n):
        lam = rng.uniform(*wl)
        th = rng.uniform(0, np.pi)
        ph = rng.uniform(0, 2 * np.pi)
        out += amp * np.sin(2 * np.pi * (x * np.cos(th) + y * np.sin(th)) / lam + ph)
    return out


def ndvi_curve(das):
    das = np.asarray(das, dtype=float)
    rise = 1 / (1 + np.exp(-(das - 32) / 7))
    sen = 1 / (1 + np.exp(-(das - 112) / 5))
    return 0.18 + 0.68 * rise * (1 - 0.8 * sen)


def sector_membership(grid: CellGrid, rng: np.random.Generator) -> np.ndarray:
    """Pertinência (0–1) ao setor sudoeste do pivô, com bordas irregulares."""
    dx, dy = grid.cx - PIVOT_CENTER[0], grid.cy - PIVOT_CENTER[1]
    r = np.hypot(dx, dy)
    ang = np.degrees(np.arctan2(dy, dx)) % 360
    wobble = _smooth_field(rng, grid.cx, grid.cy, n=5, amp=8.0, wl=(150, 400))
    da = np.abs(((ang - 222 + wobble) + 180) % 360 - 180)
    m_ang = np.clip((64 - da) / 18, 0, 1)
    m_rad = np.clip((r - 300 - wobble * 6) / 140, 0, 1)
    m = m_ang * m_rad * (grid.field_idx == 3)
    return np.clip(m * (1 + _smooth_field(rng, grid.cx, grid.cy, n=4, amp=0.12, wl=(120, 300))), 0, 1)


def t03_strip(grid: CellGrid) -> np.ndarray:
    """Faixa com desenvolvimento desuniforme no T03 (falha de estande na semeadura)."""
    d = np.abs((grid.cx - 3460) * 0.45 - (grid.cy - 1600) + 420) / np.hypot(0.45, 1)
    return np.clip((130 - d) / 60, 0, 1) * (grid.field_idx == 2)


@dataclass
class ObservationSet:
    season_idx: int
    das: int
    date: date
    ndvi: np.ndarray
    ndre: np.ndarray
    cloud: np.ndarray


def generate_observations(grid: CellGrid) -> tuple[list[ObservationSet], dict]:
    rng = np.random.default_rng(RNG_SEED)
    soil = _smooth_field(rng, grid.cx, grid.cy)                      # produtividade persistente
    sector = sector_membership(grid, rng)
    strip = t03_strip(grid)
    near_hq = np.clip((260 - np.hypot(grid.cx - 1890, grid.cy - 1450)) / 200, 0, 1) * (grid.field_idx == 4)

    sets: list[ObservationSet] = []
    for s_idx, s in enumerate(SEASONS):
        season_noise = _smooth_field(rng, grid.cx, grid.cy, n=5, amp=0.006)
        for das, d in das_dates(s):
            v = ndvi_curve(das) + s.offset + soil + season_noise - 0.03 * near_hq
            rise = 1 / (1 + np.exp(-(das - 32) / 7))
            if s.is_current:
                v -= 0.05 * strip * rise
                if das >= CURR_ANOMALY["onset"]:
                    k = min(1.0, (das - CURR_ANOMALY["onset"]) / (CURR_ANOMALY["peak"] - CURR_ANOMALY["onset"]))
                    v -= CURR_ANOMALY["depth"] * k * sector
                    v -= 0.015 * k  # veranico afeta levemente toda a fazenda
            if s.name == "2024/25":
                a = PREV_ANOMALY
                if a["onset"] <= das < a["intervention_das"]:
                    k = min(1.0, (das - a["onset"]) / (a["peak"] - a["onset"]))
                    v -= a["depth"] * k * sector
                elif das >= a["intervention_das"]:
                    k = a["residual"] + (1 - a["residual"]) * np.exp(-(das - a["intervention_das"]) / 6)
                    v -= a["depth"] * k * sector
            v = v + rng.normal(0, 0.010, v.size)
            ndre = 0.08 + 0.62 * (v - 0.18) + rng.normal(0, 0.008, v.size)

            cloud = np.zeros(v.size, dtype=bool)
            if das in s.cloud_das:
                cx0, cy0 = rng.uniform(500, 4700), rng.uniform(300, 2900)
                rx, ry = rng.uniform(900, 1600), rng.uniform(600, 1100)
                cloud = ((grid.cx - cx0) / rx) ** 2 + ((grid.cy - cy0) / ry) ** 2 < 1
                v = np.where(cloud, v * 0.35 + rng.normal(0, 0.03, v.size), v)
                ndre = np.where(cloud, ndre * 0.4, ndre)
            sets.append(ObservationSet(s_idx, das, d, np.clip(v, -0.1, 0.95), np.clip(ndre, -0.1, 0.8), cloud))

    return sets, {"sector": sector, "strip": strip}


# ---------------------------------------------------------------- clima diário sintético
def generate_weather() -> list[tuple[date, float, float, float]]:
    rng = np.random.default_rng(RNG_SEED + 1)
    out = []
    dry = {
        "2024/25": (date(2024, 12, 5), date(2024, 12, 17)),
        "2025/26": (date(2025, 12, 22), date(2026, 1, 4)),
    }
    for s in SEASONS:
        start = s.sowing - timedelta(days=20)
        end = s.sowing + timedelta(days=s.last_das + (0 if s.is_current else 5))
        d = start
        while d <= end:
            in_dry = s.name in dry and dry[s.name][0] <= d <= dry[s.name][1]
            edge = s.name in dry and d in (dry[s.name][0] - timedelta(days=1), dry[s.name][1] + timedelta(days=1))
            if edge:
                rain, tmax = float(rng.uniform(12, 28)), rng.uniform(28.5, 30.5)
            elif in_dry:
                rain, tmax = 0.0, rng.uniform(34.0, 36.5)
            else:
                rain = float(rng.gamma(1.4, 11.0)) if rng.random() < 0.55 else 0.0
                tmax = rng.uniform(29.5, 33.0) - min(rain, 30) * 0.05
            tmin = rng.uniform(20.5, 23.0)
            out.append((d, round(rain, 1), round(tmax, 1), round(tmin, 1)))
            d += timedelta(days=1)
    return out


def fields_spec() -> list[dict]:
    return _field_shapes()
