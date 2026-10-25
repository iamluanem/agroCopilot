"""Testes de integração — exigem PostGIS com seed aplicado (DATABASE_URL)."""
import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL não definido")


@pytest.fixture(scope="module")
def client():
    from app.api.main import app
    return TestClient(app)


def test_map_endpoints(client):
    farm = client.get("/api/farms").json()[0]
    assert farm["is_synthetic"]
    detail = client.get(f"/api/farms/{farm['id']}").json()
    dates = client.get(f"/api/farms/{farm['id']}/dates").json()
    assert dates[-1]["date"] == detail["reference_date"]
    risk = client.get(f"/api/farms/{farm['id']}/risk", params={"on": detail["reference_date"]}).json()
    assert risk["fields"][0]["code"] == "T04" and risk["fields"][0]["level"] == "vermelho"
    assert len(risk["cells"]["id"]) == len(risk["cells"]["level"]) > 10000
    fc = client.get(f"/api/farms/{farm['id']}/fields.geojson").json()
    assert len(fc["features"]) == 5


def test_404s(client):
    assert client.get("/api/farms/999").status_code == 404
    assert client.get("/api/farms/1/risk", params={"on": "2020-01-01"}).status_code == 404


def test_priorities_rank_t04_first_with_exposure(client):
    farm = client.get("/api/farms").json()[0]
    p = client.get(f"/api/farms/{farm['id']}/priorities").json()
    top = p["items"][0]
    assert top["code"] == "T04" and top["rank"] == 1
    assert 0 < top["economics"]["exposure_min"] < top["economics"]["exposure_max"]
    assert top["hypotheses"][0]["cause"] == "Deficiência hídrica"
    assert all(h["missing"] for h in top["hypotheses"])
    t03 = next(i for i in p["items"] if i["code"] == "T03")
    assert t03["hypotheses"][0]["cause"].startswith("Falha de estande")
    assert not next(i for i in p["items"] if i["code"] == "T01")["has_zone"]


def test_field_detail_has_memory_and_evolution(client):
    farm = client.get("/api/farms").json()[0]
    t04 = next(f for f in client.get(f"/api/farms/{farm['id']}").json()["fields"] if f["code"] == "T04")
    d = client.get(f"/api/fields/{t04['id']}").json()
    assert d["assessment"]["assessment_id"]
    assert len(d["evolution"]) > 10 and d["evolution"][-1]["vermelho"] > 30
    assert {"anomalia", "vistoria", "intervencao", "resultado"} <= {m["type"] for m in d["memory"]}
    assert client.get(f"/api/fields/{t04['id']}/memory", params={"q": "hídrica"}).json()
