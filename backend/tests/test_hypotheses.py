import numpy as np

from app.domain.hypotheses import ZoneContext, classify_pattern, rank_hypotheses


def ctx(**kw):
    base = dict(red_ha=30, yellow_ha=5, das=95, stage="R6", pattern="contiguous_sector", onset_das=88, ndvi_drop=-0.15,
                max_dry_days=14, rain_21d_mm=5, tmax_dry_mean=35, soil_texture="Oxisol, medium-to-sandy texture",
                irrigation="center pivot", recurrence_share=0.9, dry_start_das=77,
                prior_verified=[("2024/25", "Water stress")])
    base.update(kw)
    return ZoneContext(**base)


def test_dry_spell_sandy_and_history_rank_water_stress_first():
    h = rank_hypotheses(ctx())
    assert h[0].key == "water_stress"
    assert any("2024/25" in e for e in h[0].evidence)


def test_confidence_never_exceeds_moderate_without_field_check():
    assert all(h.confidence in ("low", "moderate") for h in rank_hypotheses(ctx()))


def test_early_linear_anomaly_points_to_stand_failure():
    h = rank_hypotheses(ctx(pattern="linear_strip", onset_das=35, prior_verified=[], soil_texture="clayey",
                            field_notes=["Planting skips — planter problem"]))
    assert h[0].key == "stand_failure"
    water = next(x for x in h if x.key == "water_stress")
    assert any(e.startswith("Against:") for e in water.evidence)


def test_scattered_without_drought_raises_pests():
    h = rank_hypotheses(ctx(pattern="scattered_patches", max_dry_days=2, prior_verified=[], soil_texture="clayey",
                            irrigation="rainfed"))
    assert h[0].key == "pest_disease"


def test_every_hypothesis_lists_missing_data():
    assert all(h.missing for h in rank_hypotheses(ctx()))


def test_pattern_classification():
    r, c = np.meshgrid(np.arange(10), np.arange(10))
    assert classify_pattern(r.ravel(), c.ravel())[0] == "contiguous_sector"
    d = np.arange(60)
    assert classify_pattern(np.r_[d, d], np.r_[d, d + 1])[0] == "linear_strip"
    rng = np.random.default_rng(0)
    pts = rng.choice(10000, 40, replace=False)
    assert classify_pattern(pts // 100 * 3, pts % 100 * 3)[0] == "scattered_patches"
