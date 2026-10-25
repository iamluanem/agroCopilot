"""Copiloto: DemoProvider, tool loop dos provedores LLM (HTTP simulado) e fallback. Exige banco com seed."""
import json
import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL não definido")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.api.main import app
    return TestClient(app)


def ask(client, q, **kw):
    r = client.post("/api/copilot/ask", json={"question": q, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_status_defaults_to_demo(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = client.get("/api/copilot/status").json()
    assert s["provider"] == "demo" and s["suggestions"]


@pytest.mark.parametrize("q,tool,needle", [
    ("Quais talhões precisam de atenção hoje?", "get_farm_summary", "T04"),
    ("Por que o Talhão 04 está vermelho?", "get_field_risk", "deficiência hídrica"),
    ("Qual é a perda potencial estimada no T04?", "estimate_economics", "não é perda confirmada"),
    ("Isso já aconteceu no T04? O que funcionou?", "get_intervention_outcomes", "safra 2024/25"),
    ("Como a área do T04 evoluiu depois da intervenção?", "get_intervention_outcomes", "ganho líquido"),
])
def test_demo_answers_required_questions(client, monkeypatch, q, tool, needle):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = ask(client, q)
    a = r["answer"]
    assert tool in [t["name"] for t in r["tools_used"]]
    assert needle.lower() in a["resumo"].lower()
    assert a["proxima_acao"] and a["fontes"] and any("sintétic" in x for x in a["alertas"])


def test_history_answer_carries_causal_caveat(client):
    a = ask(client, "Isso já aconteceu no T04?")["answer"]
    assert any("não prova causal" in x for x in a["alertas"])


def test_propose_then_confirm_creates_task_and_memory(client):
    client.post("/api/demo/reset")
    a = ask(client, "Crie uma vistoria para o T04")["answer"]
    t = a["tarefa_proposta"]
    assert t and t["field_code"] == "T04" and t["assessment_id"]
    before = client.get(f"/api/fields/{t['field_id']}/memory").json()
    r = client.post("/api/tasks", json={k: t[k] for k in ("field_id", "assessment_id", "title", "priority", "assignee",
                                                          "due_date", "instructions")} | {"source": "copiloto"})
    assert r.status_code == 201 and r.json()["status"] == "atribuída"
    after = client.get(f"/api/fields/{t['field_id']}/memory").json()
    try:
        new = {m["type"] for m in after}
        assert len(after) == len(before) + 2 and {"tarefa", "anomalia"} <= new
    finally:  # não deixa lixo de teste na base da demo
        client.post("/api/demo/reset")


def _mock_anthropic(monkeypatch, responses):
    calls = iter(responses)

    def handler(request: httpx.Request):
        assert request.url.path == "/v1/messages"
        body = json.loads(request.content)
        assert any(t["name"] == "responder" for t in body["tools"])
        return httpx.Response(200, json={"content": next(calls)})

    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")


def test_anthropic_tool_loop_validates_structured_answer(client, monkeypatch):
    answer = {"resumo": "T04 crítico; hipótese: deficiência hídrica.", "evidencias": ["NDVI abaixo do histórico"],
              "confianca": "moderada", "dados_faltantes": ["vistoria"], "proxima_acao": "Vistoriar", "fontes": []}
    _mock_anthropic(monkeypatch, [
        [{"type": "tool_use", "id": "a", "name": "get_field_risk", "input": {"field": "T04"}}],
        [{"type": "tool_use", "id": "b", "name": "responder", "input": answer}],
    ])
    r = ask(client, "Por que o T04 está vermelho?")
    assert r["provider"].startswith("Claude")
    assert [t["name"] for t in r["tools_used"]] == ["get_field_risk"]
    assert r["answer"]["resumo"] == answer["resumo"]


def test_provider_failure_falls_back_to_demo(client, monkeypatch):
    _mock_anthropic(monkeypatch, [[{"type": "tool_use", "id": "x", "name": "responder", "input": {"bad": 1}}]] * 0)
    r = ask(client, "Por que o T04 está vermelho?")
    assert r["provider"].startswith("DemoProvider")
    assert "indisponível" in r["answer"]["alertas"][0]
