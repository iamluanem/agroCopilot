import numpy as np

from app.domain.risk import LEVEL_CODE, compute_cell_risk
from app.infrastructure.seed import scenario as sc


def _setup():
    specs = sc.fields_spec()
    grid = sc.build_grid(specs, 30)
    obs, meta = sc.generate_observations(grid)
    return specs, grid, obs, meta


def test_farm_area_and_cells_inside_fields():
    specs, grid, _, _ = _setup()
    assert 1150 < grid.area_ha.sum() < 1250
    for i, f in enumerate(specs):
        cells = [g for g, fi in zip(grid.geoms, grid.field_idx) if fi == i]
        assert all(f["geom"].buffer(0.01).contains(c) for c in cells)
        assert abs(sum(c.area for c in cells) / 1e4 - f["geom"].area / 1e4) < 2


def test_generation_is_deterministic():
    _, g, a, _ = _setup()
    _, _, b, _ = _setup()
    assert np.array_equal(a[-1].ndvi, b[-1].ndvi)


def test_reference_date_tells_the_demo_story():
    _, grid, obs, _ = _setup()
    cur = [o for o in obs if o.season_idx == 2][-1]
    prev = np.array([np.where(o.cloud, np.nan, o.ndvi) for o in obs if o.season_idx < 2 and o.das == cur.das])
    r = compute_cell_risk(cur.ndvi, np.nanmean(prev, 0), grid.field_idx, cur.cloud, np.full(cur.ndvi.size, 3))
    red = lambda i: grid.area_ha[(grid.field_idx == i) & (r.level == LEVEL_CODE["red"])].sum()
    yellow = lambda i: grid.area_ha[(grid.field_idx == i) & (r.level == LEVEL_CODE["yellow"])].sum()
    assert 30 <= red(3) <= 45           # F04: red cluster ~38 ha
    assert red(2) < 10 and yellow(2) + red(2) >= 15  # F03: watch
    for i in (0, 1, 4):
        assert red(i) < 2               # F01, F02, F05 healthy
