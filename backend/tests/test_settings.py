import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL não definido")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.api.main import app
    c = TestClient(app)
    original = c.get("/api/settings").json()
    yield c
    c.put("/api/settings", json={k: original[k] for k in ("economia", "risco", "llm_provider")})


def _t04(c):
    farm = c.get("/api/farms").json()[0]
    return farm, next(i for i in c.get(f"/api/farms/{farm['id']}/priorities").json()["items"] if i["code"] == "T04")


def test_price_change_recomputes_exposure_and_keeps_old_version(client):
    s = client.get("/api/settings").json()
    _, before = _t04(client)
    econ = {**s["economia"], "preco_saca_rs": s["economia"]["preco_saca_rs"] * 1.5}
    r = client.put("/api/settings", json={"economia": econ, "risco": s["risco"], "llm_provider": s["llm_provider"]})
    assert r.status_code == 200
    _, after = _t04(client)
    assert after["economics"]["exposure_max"] == pytest.approx(before["economics"]["exposure_max"] * 1.5, rel=0.01)
    assert after["assessment_id"] != before["assessment_id"]
    farm_id = client.get("/api/farms").json()[0]["id"]
    assert client.get(f"/api/fields/{before['field_id']}/assessment", params={"on": before["date"]}).json()["assessment_id"] == after["assessment_id"]
    del farm_id


def test_stricter_thresholds_shrink_red_area(client):
    s = client.get("/api/settings").json()
    _, before = _t04(client)
    risco = {**s["risco"], "limiar_vermelho": 6.0}
    client.put("/api/settings", json={"economia": s["economia"], "risco": risco, "llm_provider": s["llm_provider"]})
    _, after = _t04(client)
    assert after["red_ha"] < before["red_ha"]


@pytest.mark.parametrize("patch", [
    {"economia": {"perda_min_pct": 30, "perda_max_pct": 10}},
    {"risco": {"limiar_amarelo": 3, "limiar_vermelho": 2}},
    {"llm_provider": "gpt-qualquer"},
])
def test_invalid_settings_rejected(client, patch):
    s = client.get("/api/settings").json()
    body = {"economia": s["economia"], "risco": s["risco"], "llm_provider": s["llm_provider"]}
    for k, v in patch.items():
        body[k] = {**body[k], **v} if isinstance(v, dict) else v
    assert client.put("/api/settings", json=body).status_code == 422
