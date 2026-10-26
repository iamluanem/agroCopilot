"""Baixa uma cena REAL do Sentinel-2 L2A (Earth Search, gratuito, sem chave) para a área da fazenda e gera
camadas NDVI e NDRE prontas para o mapa.

Uso (dentro do container da API):
    python scripts/fetch_sentinel.py                       # últimos 120 dias, nuvem ≤ 20%
    python scripts/fetch_sentinel.py --start 2026-01-01 --end 2026-02-28 --max-cloud 10
    python scripts/fetch_sentinel.py --bbox -55.88 -12.62 -55.82 -12.57   # sem banco

Saída em $MEDIA_DIR/sentinel/: <cena>.json (metadados), <cena>_ndvi.png e <cena>_ndre.png (EPSG:4326).
A API lista as cenas em /api/farms/{id}/imagery e o mapa mostra a camada "Sentinel-2 real".

Importante: os limites dos talhões da demo são sintéticos; a imagem é real. Use a camada para mostrar o pipeline
de dados reais, não para tirar conclusões sobre os talhões da demo.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from PIL import Image

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
SCL_INVALID = {0, 1, 3, 8, 9, 10, 11}  # sem dado, saturado, sombra de nuvem, nuvens, cirrus, neve
RAMPS = {
    "ndvi": [(0.3, "#a50026"), (0.55, "#f46d43"), (0.7, "#fee08b"), (0.8, "#a6d96a"), (0.9, "#1a9850")],
    "ndre": [(0.2, "#a50026"), (0.32, "#f46d43"), (0.4, "#fee08b"), (0.46, "#a6d96a"), (0.52, "#1a9850")],
}
# nomes dos assets no Earth Search v1 (com fallback para códigos de banda)
ASSETS = {"red": ("red", "B04"), "nir": ("nir", "B08"), "rededge1": ("rededge1", "B05"), "nir08": ("nir08", "B8A"),
          "scl": ("scl", "SCL")}


# ------------------------------------------------------------------ grade e leitura
def target_grid(bbox: tuple[float, float, float, float], res_deg: float):
    from rasterio.transform import from_origin
    w, s, e, n = bbox
    width, height = int(np.ceil((e - w) / res_deg)), int(np.ceil((n - s) / res_deg))
    return from_origin(w, n, res_deg, res_deg), width, height


def read_to_grid(href: str, grid, nearest: bool = False) -> np.ndarray:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    transform, width, height = grid
    with rasterio.open(href) as src, WarpedVRT(
        src, crs="EPSG:4326", transform=transform, width=width, height=height,
        resampling=Resampling.nearest if nearest else Resampling.bilinear, nodata=0,
    ) as vrt:
        return vrt.read(1).astype("float32")


def _asset(assets: dict, key: str) -> dict:
    for name in ASSETS[key]:
        if name in assets:
            return assets[name]
    raise KeyError(f"Banda '{key}' não encontrada na cena (assets: {', '.join(assets)})")


def reflectance(a: dict, raw: np.ndarray) -> np.ndarray:
    """Aplica scale/offset do STAC (raster:bands). Baseline ≥ 04.00 tem offset −0,1."""
    band = (a.get("raster:bands") or [{}])[0]
    scale, offset = band.get("scale", 0.0001), band.get("offset", 0.0)
    out = raw * scale + offset
    out[raw == 0] = np.nan
    return out


def index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        v = (b - a) / (b + a)
    return np.where(np.isfinite(v), np.clip(v, -1, 1), np.nan)


def colorize(v: np.ndarray, ramp: list[tuple[float, str]], mask: np.ndarray) -> Image.Image:
    stops = np.array([s for s, _ in ramp])
    cols = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for _, c in ramp], dtype=float)
    x = np.clip(np.nan_to_num(v, nan=stops[0]), stops[0], stops[-1])
    rgb = np.stack([np.interp(x, stops, cols[:, k]) for k in range(3)], axis=-1)
    alpha = np.where(mask & np.isfinite(v), 215, 0)
    return Image.fromarray(np.dstack([rgb, alpha]).astype("uint8"), "RGBA")


def process(assets: dict, bbox, out_dir: Path, meta: dict, res_deg: float = 0.0001) -> dict:
    """Lê bandas, aplica máscara SCL, calcula NDVI (B08/B04) e NDRE (B8A/B05) e grava PNGs + JSON."""
    grid = target_grid(bbox, res_deg)
    red = reflectance(_asset(assets, "red"), read_to_grid(_asset(assets, "red")["href"], grid))
    nir = reflectance(_asset(assets, "nir"), read_to_grid(_asset(assets, "nir")["href"], grid))
    re1 = reflectance(_asset(assets, "rededge1"), read_to_grid(_asset(assets, "rededge1")["href"], grid))
    n08 = reflectance(_asset(assets, "nir08"), read_to_grid(_asset(assets, "nir08")["href"], grid))
    try:
        scl = read_to_grid(_asset(assets, "scl")["href"], grid, nearest=True)
        valid = ~np.isin(scl.astype(int), list(SCL_INVALID))
    except KeyError:
        valid = np.ones(red.shape, dtype=bool)
    ndvi, ndre = index(red, nir), index(re1, n08)
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = meta["scene_id"]
    files = {}
    for name, arr in (("ndvi", ndvi), ("ndre", ndre)):
        fn = f"{sid}_{name}.png"
        colorize(arr, RAMPS[name], valid).save(out_dir / fn, optimize=True)
        files[name] = f"/media/sentinel/{fn}"
    ok = valid & np.isfinite(ndvi)
    record = {
        **meta, "bounds": list(bbox), "files": files, "resolution_deg": res_deg,
        "valid_pct": round(float(ok.mean()) * 100, 1),
        "ndvi_mean": round(float(np.nanmean(np.where(ok, ndvi, np.nan))), 3) if ok.any() else None,
        "ndre_mean": round(float(np.nanmean(np.where(ok, ndre, np.nan))), 3) if ok.any() else None,
        "source": "Sentinel-2 L2A (Copernicus) via Earth Search", "is_synthetic": False,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / f"{sid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return record


# ------------------------------------------------------------------ STAC
def search(bbox, start: date, end: date, max_cloud: float):
    from pystac_client import Client
    items = list(Client.open(STAC_URL).search(
        collections=[COLLECTION], bbox=bbox, datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=50,
    ).items())
    # precisa cobrir a fazenda inteira: prioriza menor nuvem, depois mais recente
    items.sort(key=lambda it: (it.properties.get("eo:cloud_cover", 100), -it.datetime.timestamp()))
    return items


def farm_bbox(margin: float) -> tuple[tuple[float, float, float, float], int]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import text

    from app.infrastructure.db.base import SessionLocal
    with SessionLocal() as s:
        row = s.execute(text("""
            SELECT f.farm_id, ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
            FROM (SELECT farm_id, ST_Extent(geom) e FROM fields GROUP BY farm_id ORDER BY farm_id LIMIT 1) f
        """)).first()
    if not row:
        raise SystemExit("Nenhuma fazenda no banco. Rode o seed ou use --bbox.")
    return (row[1] - margin, row[2] - margin, row[3] + margin, row[4] + margin), row[0]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    p.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=120))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--max-cloud", type=float, default=20)
    p.add_argument("--margin", type=float, default=0.01, help="margem em graus ao redor da fazenda")
    p.add_argument("--out", type=Path, default=Path(os.getenv("MEDIA_DIR", "media")) / "sentinel")
    a = p.parse_args(argv)

    if a.bbox:
        bbox, farm_id = tuple(a.bbox), None
    else:
        bbox, farm_id = farm_bbox(a.margin)
    print(f"Buscando Sentinel-2 L2A em {bbox} de {a.start} a {a.end} (nuvem < {a.max_cloud}%)…")
    items = search(bbox, a.start, a.end, a.max_cloud)
    if not items:
        print("Nenhuma cena encontrada. Aumente o período (--start) ou o limite de nuvem (--max-cloud).")
        return 1
    it = items[0]
    meta = {"scene_id": it.id, "datetime": it.datetime.isoformat(), "date": it.datetime.date().isoformat(),
            "cloud_cover": it.properties.get("eo:cloud_cover"), "platform": it.properties.get("platform"),
            "mgrs_tile": it.properties.get("s2:mgrs_tile") or it.properties.get("grid:code"), "farm_id": farm_id,
            "stac_item": f"{STAC_URL}/collections/{COLLECTION}/items/{it.id}"}
    print(f"Cena escolhida: {it.id} ({meta['date']}, nuvem {meta['cloud_cover']}%). Processando…")
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    assets = {k: {"href": v.href, **v.extra_fields} for k, v in it.assets.items()}
    rec = process(assets, bbox, a.out, meta)
    print(f"Pronto: NDVI médio {rec['ndvi_mean']}, {rec['valid_pct']}% de pixels válidos. Arquivos em {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
