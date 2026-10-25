import pytest

from app.domain import economics as eco


def test_exposure_formula_and_range():
    a = eco.EconomicAssumptions(produtividade_esperada_sc_ha=60, preco_saca_rs=100, perda_min_pct=10, perda_max_pct=20,
                                custo_vistoria_rs=500, custo_intervencao_rs_ha=50)
    e = eco.estimate_exposure(red_ha=10, yellow_ha=4, a=a)  # 10 + 0,5×4 = 12 ha
    assert e.affected_ha == 12
    assert e.gross_value_rs == 12 * 60 * 100
    assert (e.exposure_min, e.exposure_max) == (7200, 14400)
    assert e.intervention_cost == 600 and e.inspection_cost == 500
    assert e.assumptions["area_critica_ha"] == 10


def test_assumptions_from_partial_dict():
    a = eco.EconomicAssumptions.from_dict({"preco_saca_rs": "130"})
    assert a.preco_saca_rs == 130 and a.produtividade_esperada_sc_ha == 62


@pytest.mark.parametrize("das,expected", [(20, 0.4), (50, 0.7), (80, 1.0), (105, 0.7), (118, 0.4)])
def test_urgency_by_stage(das, expected):
    assert eco.urgency(das, worsening=False)[0] == expected


def test_worsening_raises_urgency_capped():
    assert eco.urgency(50, True)[0] == 0.85
    assert eco.urgency(80, True)[0] == 1.0


def test_priority_weights_confidence():
    assert eco.priority_score(1000, 1.0, "alta") > eco.priority_score(1000, 1.0, "moderada") > \
        eco.priority_score(1000, 1.0, "baixa")
