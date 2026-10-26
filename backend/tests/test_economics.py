import pytest

from app.domain import economics as eco


def test_exposure_formula_and_range():
    a = eco.EconomicAssumptions(expected_yield_bags_ha=60, bag_price_brl=100, loss_min_pct=10, loss_max_pct=20,
                                inspection_cost_brl=500, intervention_cost_brl_ha=50)
    e = eco.estimate_exposure(red_ha=10, yellow_ha=4, a=a)  # 10 + 0.5×4 = 12 ha
    assert e.affected_ha == 12
    assert e.gross_value_brl == 12 * 60 * 100
    assert (e.exposure_min, e.exposure_max) == (7200, 14400)
    assert e.intervention_cost == 600 and e.inspection_cost == 500
    assert e.assumptions["critical_area_ha"] == 10


def test_assumptions_from_partial_dict():
    a = eco.EconomicAssumptions.from_dict({"bag_price_brl": "130"})
    assert a.bag_price_brl == 130 and a.expected_yield_bags_ha == 62


@pytest.mark.parametrize("das,expected", [(20, 0.4), (50, 0.7), (80, 1.0), (105, 0.7), (118, 0.4)])
def test_urgency_by_stage(das, expected):
    assert eco.urgency(das, worsening=False)[0] == expected


def test_worsening_raises_urgency_capped():
    assert eco.urgency(50, True)[0] == 0.85
    assert eco.urgency(80, True)[0] == 1.0


def test_priority_weights_confidence():
    assert eco.priority_score(1000, 1.0, "high") > eco.priority_score(1000, 1.0, "moderate") > \
        eco.priority_score(1000, 1.0, "low")
