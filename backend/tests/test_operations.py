"""Demo script, steps 6→10: task → inspection → verification → intervention → simulation → outcome → memory."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.api.main import app
    c = TestClient(app)
    c.post("/api/demo/reset")
    yield c
    c.post("/api/demo/reset")


def _t04(client):
    farm = client.get("/api/farms").json()[0]
    p = client.get(f"/api/farms/{farm['id']}/priorities").json()
    return farm, next(i for i in p["items"] if i["code"] == "F04")


def test_full_closed_loop(client):
    farm, a = _t04(client)
    # 6. create an inspection from the assessment
    t = client.post("/api/tasks", json={"field_id": a["field_id"], "assessment_id": a["assessment_id"],
                                        "title": "Inspection F04", "assignee": "Carlos", "source": "map"}).json()
    assert t["status"] == "assigned"
    assert client.patch(f"/api/tasks/{t['id']}/status", json={"status": "in_progress"}).status_code == 200
    # cannot complete without recording the inspection
    assert client.patch(f"/api/tasks/{t['id']}/status", json={"status": "completed"}).status_code == 422
    # an intervention before verification is blocked
    # 7. inspection with a photo
    r = client.post(f"/api/tasks/{t['id']}/inspection", json={
        "findings": "Midday wilting; clogged sprinklers.", "verified_cause": "Water stress",
        "recorded_by": "Carlos", "photos": [PNG]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "completed" and d["inspection"]["photos"][0].startswith("/media/")
    assert client.get(d["inspection"]["photos"][0]).status_code == 200
    insp_id = d["inspection"]["id"]
    blocked = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                      "approved_action": "Irrigation depth adjustment", "approved_by": "Eng.",
                                                      "actual_cost": 100})
    assert blocked.status_code == 422
    assert client.post(f"/api/tasks/{t['id']}/verify", json={"verified_by": "Mariana Rocha, agronomist"}).json()["status"] == "verified"
    # chemicals without a prescription are blocked
    chem = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                   "approved_action": "Apply insecticide 0.5 L/ha", "approved_by": "Eng.",
                                                   "actual_cost": 100})
    assert chem.status_code == 422 and "prescription" in chem.json()["detail"]
    # 8. approved intervention
    iv = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                 "approved_action": "Unclog sprinklers and raise irrigation depth in the SW sector.",
                                                 "approved_by": "Eng. Agr. Mariana", "actual_cost": 3400}).json()
    # 9. simulation + outcome
    r = client.post(f"/api/interventions/{iv['id']}/simulate")
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["outcome"]["delta_vs_comparison"] > 0
    assert "SIMULATED" in o["outcome"]["limitations"] and "not proof of causation" in o["outcome"]["limitations"]
    assert any(p["simulated"] for p in o["series"])
    dates = client.get(f"/api/farms/{farm['id']}/dates").json()
    assert dates[-1]["simulated"] and client.get(f"/api/farms/{farm['id']}/risk", params={"on": dates[-1]["date"]}).json()["simulated"]
    assert client.get("/api/outcomes").json()[0]["id"] == o["outcome"]["id"]
    # 10. memory with the new cycle
    mem = client.get(f"/api/fields/{a['field_id']}/memory").json()
    cur = [m["type"] for m in mem if m["season"] == "2025/26"]
    assert {"anomaly", "task", "inspection", "intervention", "outcome"} <= set(cur)
    # the copilot sees the new outcome
    ans = client.post("/api/copilot/ask", json={"question": "How did the F04 area evolve after the intervention?"}).json()
    assert "simulated" in ans["answer"]["summary"]
    hist = client.post("/api/copilot/ask", json={"question": "Has this happened in F04 before?"}).json()
    assert "2024/25" in hist["answer"]["summary"]


def test_reset_restores_demo(client):
    client.post("/api/demo/reset")
    farm = client.get("/api/farms").json()[0]
    assert not any(d["simulated"] for d in client.get(f"/api/farms/{farm['id']}/dates").json())
    assert all(t["is_synthetic"] for t in client.get("/api/tasks").json())
