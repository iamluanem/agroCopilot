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
