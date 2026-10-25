import numpy as np

from app.domain.risk import LEVEL_CODE, RiskThresholds, compute_cell_risk, field_level


def _base(n=200, seed=1):
    rng = np.random.default_rng(seed)
    ndvi = 0.82 + rng.normal(0, 0.01, n)
    return ndvi, ndvi + rng.normal(0, 0.005, n), np.zeros(n, int), np.zeros(n, bool), np.full(n, 3)


def test_homogeneous_field_is_green():
    r = compute_cell_risk(*_base())
    assert (r.level == LEVEL_CODE["verde"]).mean() > 0.95


def test_local_drop_vs_history_and_field_is_red_with_high_confidence():
    ndvi, base, fid, cloud, rv = _base()
    ndvi[:20] -= 0.2
    r = compute_cell_risk(ndvi, base, fid, cloud, rv)
    assert (r.level[:20] == LEVEL_CODE["vermelho"]).all()
    assert (r.confidence[:20] == 2).all()


def test_farm_wide_shift_is_not_flagged():
    ndvi, base, fid, cloud, rv = _base()
    r = compute_cell_risk(ndvi - 0.05, base, fid, cloud, rv)
    assert (r.level == LEVEL_CODE["vermelho"]).sum() == 0


def test_cloudy_cells_have_no_data():
    ndvi, base, fid, cloud, rv = _base()
    cloud[:10] = True
    r = compute_cell_risk(ndvi, base, fid, cloud, rv)
    assert (r.level[:10] == LEVEL_CODE["sem_dado"]).all()
    assert (r.confidence[:10] == -1).all()


def test_without_history_confidence_drops():
    ndvi, _, fid, cloud, rv = _base()
    ndvi[:20] -= 0.2
    r = compute_cell_risk(ndvi, np.full(ndvi.size, np.nan), fid, cloud, rv)
    assert (r.level[:20] == LEVEL_CODE["vermelho"]).all()
    assert (r.confidence[:20] < 2).all()


def test_thresholds_are_configurable():
    ndvi, base, fid, cloud, rv = _base()
    ndvi[:20] -= 0.2
    r = compute_cell_risk(ndvi, base, fid, cloud, rv, RiskThresholds(yellow=50, red=100))
    assert (r.level == LEVEL_CODE["verde"]).all()


def test_field_level_rules():
    assert field_level({"vermelho": 12}) == "vermelho"
    assert field_level({"vermelho": 2, "amarelo": 14}) == "amarelo"
    assert field_level({"amarelo": 4}) == "verde"
