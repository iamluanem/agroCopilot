"""Sentinel-2 pipeline with local synthetic bands (no network): reprojection, scale/offset, SCL mask and PNGs."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402

spec = importlib.util.spec_from_file_location("fetch_sentinel", Path(__file__).parents[1] / "scripts" / "fetch_sentinel.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)

BBOX = (-55.89, -12.63, -55.82, -12.57)


def _band(path: Path, data: np.ndarray, res: float):
    # UTM 21S cobrindo a bbox (canto NO aproximado), como as COGs do Sentinel-2
    t = from_origin(618_000, 8_612_000, res, res)
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
                       dtype=data.dtype, crs="EPSG:32721", transform=t, nodata=0) as dst:
        dst.write(data, 1)


@pytest.fixture()
def scene(tmp_path):
    n10, n20 = 1100, 550
    yy, xx = np.mgrid[0:n10, 0:n10]
    stress = (xx < 350)  # western strip with weaker vegetation
    red = np.where(stress, 2000, 1300).astype("uint16")       # DN com offset de 1000 (baseline ≥ 04.00)
    nir = np.where(stress, 3800, 5200).astype("uint16")
    re1 = np.full((n20, n20), 1900, "uint16")
    n08 = np.full((n20, n20), 4600, "uint16")
    scl = np.full((n20, n20), 4, "uint8")
    scl[100:160, :] = 9  # faixa de nuvem dentro da bbox
    for name, arr, res in (("red", red, 10), ("nir", nir, 10), ("rededge1", re1, 20), ("nir08", n08, 20), ("scl", scl, 20)):
        _band(tmp_path / f"{name}.tif", arr, res)
    rb = {"raster:bands": [{"scale": 0.0001, "offset": -0.1}]}
    assets = {k: {"href": str(tmp_path / f"{k}.tif"), **(rb if k != "scl" else {})} for k in ("red", "nir", "rededge1", "nir08", "scl")}
    return assets, tmp_path


def test_process_generates_layers_and_metadata(scene):
    assets, tmp = scene
    rec = fs.process(assets, BBOX, tmp / "out", {"scene_id": "S2_TEST", "date": "2026-01-20", "farm_id": 1})
    assert (tmp / "out" / "S2_TEST_ndvi.png").exists() and (tmp / "out" / "S2_TEST_ndre.png").exists()
    meta = json.loads((tmp / "out" / "S2_TEST.json").read_text())
    assert meta["files"]["ndvi"] == "/media/sentinel/S2_TEST_ndvi.png" and meta["is_synthetic"] is False
    # −0.1 offset applied: healthy NDVI = (0.42−0.03)/(0.42+0.03) ≈ 0.87
    assert 0.6 < meta["ndvi_mean"] < 0.9
    assert 0 < meta["valid_pct"] < 100  # nuvem mascarada pelo SCL e borda sem dado


def test_index_and_reflectance():
    r = fs.reflectance({"raster:bands": [{"scale": 0.0001, "offset": -0.1}]}, np.array([0, 1100, 4100], "float32"))
    assert np.isnan(r[0]) and r[1] == pytest.approx(0.01) and r[2] == pytest.approx(0.31)
    assert fs.index(np.array([0.05]), np.array([0.45]))[0] == pytest.approx(0.8)
