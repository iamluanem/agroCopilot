"""Copiloto: DemoProvider, tool loop dos provedores LLM (HTTP simulado) e fallback. Exige banco com seed."""
import json
import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")


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
    ("Which fields need attention today?", "get_farm_summary", "F04"),
    ("Why is Field 04 red?", "get_field_risk", "water stress"),
    ("What is the estimated potential loss in F04?", "estimate_economics", "not a confirmed loss"),
    ("Has this happened in F04 before? What worked?", "get_intervention_outcomes", "2024/25 season"),
    ("How did the F04 area evolve after the intervention?", "get_intervention_outcomes", "a gain of"),
])
def test_demo_answers_required_questions(client, monkeypatch, q, tool, needle):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = ask(client, q)
    a = r["answer"]
    assert tool in [t["name"] for t in r["tools_used"]]
    assert needle.lower() in a["summary"].lower()
    assert a["next_action"] and a["sources"] and any("synthetic" in x.lower() for x in a["warnings"])


def test_history_answer_carries_causal_caveat(client):
    a = ask(client, "Has this happened in F04 before?")["answer"]
    assert any("not proof of causation" in x for x in a["warnings"])


def test_propose_then_confirm_creates_task_and_memory(client):
    client.post("/api/demo/reset")
    a = ask(client, "Create an inspection for F04")["answer"]
    t = a["proposed_task"]
    assert t and t["field_code"] == "F04" and t["assessment_id"]
    before = client.get(f"/api/fields/{t['field_id']}/memory").json()
    r = client.post("/api/tasks", json={k: t[k] for k in ("field_id", "assessment_id", "title", "priority", "assignee",
                                                          "due_date", "instructions")} | {"source": "copiloto"})
    assert r.status_code == 201 and r.json()["status"] == "assigned"
    after = client.get(f"/api/fields/{t['field_id']}/memory").json()
    try:
        new = {m["type"] for m in after}
        assert len(after) == len(before) + 2 and {"task", "anomaly"} <= new
    finally:  # leave no test data in the demo database
        client.post("/api/demo/reset")


def _mock_anthropic(monkeypatch, responses):
    calls = iter(responses)

    def handler(request: httpx.Request):
        assert request.url.path == "/v1/messages"
        body = json.loads(request.content)
        assert any(t["name"] == "respond" for t in body["tools"])
        return httpx.Response(200, json={"content": next(calls)})

    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")


def test_anthropic_tool_loop_validates_structured_answer(client, monkeypatch):
    answer = {"summary": "F04 critical; hypothesis: water stress.", "evidence": ["NDVI below history"],
              "confidence": "moderate", "missing_data": ["inspection"], "next_action": "Inspect", "sources": []}
    _mock_anthropic(monkeypatch, [
        [{"type": "tool_use", "id": "a", "name": "get_field_risk", "input": {"field": "F04"}}],
        [{"type": "tool_use", "id": "b", "name": "respond", "input": answer}],
    ])
    r = ask(client, "Why is F04 red?")
    assert r["provider"].startswith("Claude")
    assert [t["name"] for t in r["tools_used"]] == ["get_field_risk"]
    assert r["answer"]["summary"] == answer["summary"]


def test_provider_failure_falls_back_to_demo(client, monkeypatch):
    _mock_anthropic(monkeypatch, [[{"type": "tool_use", "id": "x", "name": "respond", "input": {"bad": 1}}]] * 0)
    r = ask(client, "Why is F04 red?")
    assert r["provider"].startswith("DemoProvider")
    assert "unavailable" in r["answer"]["warnings"][0]
