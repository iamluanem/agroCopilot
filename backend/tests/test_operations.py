"""Roteiro da demo, passos 6→10: tarefa → vistoria → verificação → intervenção → simulação → resultado → memória."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL não definido")

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
    return farm, next(i for i in p["items"] if i["code"] == "T04")


def test_full_closed_loop(client):
    farm, a = _t04(client)
    # 6. cria vistoria a partir da avaliação
    t = client.post("/api/tasks", json={"field_id": a["field_id"], "assessment_id": a["assessment_id"],
                                        "title": "Vistoria T04", "assignee": "Carlos", "source": "mapa"}).json()
    assert t["status"] == "atribuída"
    assert client.patch(f"/api/tasks/{t['id']}/status", json={"status": "em_andamento"}).status_code == 200
    # não pode concluir sem registrar vistoria
    assert client.patch(f"/api/tasks/{t['id']}/status", json={"status": "concluída"}).status_code == 422
    # intervenção antes da verificação é bloqueada
    # 7. vistoria com foto
    r = client.post(f"/api/tasks/{t['id']}/inspection", json={
        "findings": "Murcha nas horas quentes; emissores entupidos.", "verified_cause": "Deficiência hídrica",
        "recorded_by": "Carlos", "photos": [PNG]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "concluída" and d["inspection"]["photos"][0].startswith("/media/")
    assert client.get(d["inspection"]["photos"][0]).status_code == 200
    insp_id = d["inspection"]["id"]
    blocked = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                      "approved_action": "Ajuste da lâmina", "approved_by": "Eng.",
                                                      "actual_cost": 100})
    assert blocked.status_code == 422
    assert client.post(f"/api/tasks/{t['id']}/verify", json={"verified_by": "Eng. Agr. Mariana"}).json()["status"] == "verificada"
    # química sem receituário é bloqueada
    chem = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                   "approved_action": "Aplicar inseticida 0,5 L/ha", "approved_by": "Eng.",
                                                   "actual_cost": 100})
    assert chem.status_code == 422 and "receituário" in chem.json()["detail"]
    # 8. intervenção aprovada
    iv = client.post("/api/interventions", json={"field_id": a["field_id"], "inspection_id": insp_id,
                                                 "approved_action": "Desentupir emissores e aumentar lâmina no setor SO.",
                                                 "approved_by": "Eng. Agr. Mariana", "actual_cost": 3400}).json()
    # 9. simulação + resultado
    r = client.post(f"/api/interventions/{iv['id']}/simulate")
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["outcome"]["delta_vs_comparison"] > 0
    assert "SIMULADAS" in o["outcome"]["limitations"] and "não prova causal" in o["outcome"]["limitations"]
    assert any(p["simulated"] for p in o["series"])
    dates = client.get(f"/api/farms/{farm['id']}/dates").json()
    assert dates[-1]["simulated"] and client.get(f"/api/farms/{farm['id']}/risk", params={"on": dates[-1]["date"]}).json()["simulated"]
    assert client.get("/api/outcomes").json()[0]["id"] == o["outcome"]["id"]
    # 10. memória com o ciclo novo
    mem = client.get(f"/api/fields/{a['field_id']}/memory").json()
    cur = [m["type"] for m in mem if m["season"] == "2025/26"]
    assert {"anomalia", "tarefa", "vistoria", "intervencao", "resultado"} <= set(cur)
    # copiloto enxerga o resultado novo
    ans = client.post("/api/copilot/ask", json={"question": "Como a área do T04 evoluiu depois da intervenção?"}).json()
    assert "simuladas" in ans["answer"]["resumo"]
    hist = client.post("/api/copilot/ask", json={"question": "Isso já aconteceu no T04?"}).json()
    assert "2024/25" in hist["answer"]["resumo"]


def test_reset_restores_demo(client):
    client.post("/api/demo/reset")
    farm = client.get("/api/farms").json()[0]
    assert not any(d["simulated"] for d in client.get(f"/api/farms/{farm['id']}/dates").json())
    assert all(t["is_synthetic"] for t in client.get("/api/tasks").json())
