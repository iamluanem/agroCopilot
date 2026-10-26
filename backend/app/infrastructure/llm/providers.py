"""LLM providers with tool calling. The model only reads data through tools and finishes by calling `respond`,
whose input is validated against the CopilotAnswer schema (Pydantic)."""
import json
import os

import httpx
from pydantic import ValidationError

from app.application.copilot_tools import TOOLS, ToolContext, run_tool
from app.domain.copilot import SYSTEM_PROMPT, CopilotAnswer, CopilotRequest, ToolCall

MAX_STEPS = 8
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
RESPOND_SCHEMA = CopilotAnswer.model_json_schema()


class ProviderError(RuntimeError):
    pass


def _context_note(req: CopilotRequest, ctx: ToolContext) -> str:
    note = f"Reference date: {ctx.ref.isoformat()}. Fields: {', '.join(f.code for f in ctx.farm.fields)}."
    if req.field_id:
        f = next((x for x in ctx.farm.fields if x.id == req.field_id), None)
        if f:
            note += f" Field in context on screen: {f.code}."
    return note


def _history(req: CopilotRequest) -> list[dict]:
    return [{"role": h["role"], "content": str(h["content"])} for h in req.history[-8:]
            if h.get("role") in ("user", "assistant") and h.get("content")]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self.key = os.environ["ANTHROPIC_API_KEY"]
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.label = f"Claude ({self.model})"

    def answer(self, req: CopilotRequest, ctx: ToolContext) -> tuple[CopilotAnswer, list[ToolCall]]:
        tools = [{"name": n, "description": d, "input_schema": sch} for n, (_, d, sch) in TOOLS.items()]
        tools.append({"name": "respond", "description": "Delivers the final structured answer to the user.",
                      "input_schema": RESPOND_SCHEMA})
        msgs = _history(req) + [{"role": "user", "content": f"{_context_note(req, ctx)}\n\nQuestion: {req.question}"}]
        calls: list[ToolCall] = []
        with httpx.Client(timeout=TIMEOUT) as http:
            for step in range(MAX_STEPS):
                body = {"model": self.model, "max_tokens": 2048, "system": SYSTEM_PROMPT, "messages": msgs,
                        "tools": tools, "tool_choice": {"type": "any"}}
                r = http.post("https://api.anthropic.com/v1/messages", json=body,
                              headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
                if r.status_code != 200:
                    raise ProviderError(f"Anthropic {r.status_code}: {r.text[:300]}")
                content = r.json()["content"]
                msgs.append({"role": "assistant", "content": content})
                results = []
                for block in content:
                    if block.get("type") != "tool_use":
                        continue
                    if block["name"] == "respond":
                        try:
                            return CopilotAnswer.model_validate(block["input"]), calls
                        except ValidationError as e:
                            results.append({"type": "tool_result", "tool_use_id": block["id"], "is_error": True,
                                            "content": f"Answer does not match the schema: {e}"})
                            continue
                    calls.append(ToolCall(name=block["name"], args=block["input"]))
                    out = run_tool(ctx, block["name"], block["input"])
                    results.append({"type": "tool_result", "tool_use_id": block["id"],
                                    "content": json.dumps(out, ensure_ascii=False, default=str)[:20000]})
                msgs.append({"role": "user", "content": results})
        raise ProviderError("The model did not finish its answer within the step limit.")


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self.key = os.environ["OPENAI_API_KEY"]
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.label = f"OpenAI ({self.model})"

    def answer(self, req: CopilotRequest, ctx: ToolContext) -> tuple[CopilotAnswer, list[ToolCall]]:
        tools = [{"type": "function", "function": {"name": n, "description": d, "parameters": sch}}
                 for n, (_, d, sch) in TOOLS.items()]
        tools.append({"type": "function", "function": {"name": "respond", "parameters": RESPOND_SCHEMA,
                                                       "description": "Delivers the final structured answer to the user."}})
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + _history(req) + [
            {"role": "user", "content": f"{_context_note(req, ctx)}\n\nQuestion: {req.question}"}]
        calls: list[ToolCall] = []
        with httpx.Client(timeout=TIMEOUT) as http:
            for step in range(MAX_STEPS):
                r = http.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                              json={"model": self.model, "messages": msgs, "tools": tools, "tool_choice": "required"})
                if r.status_code != 200:
                    raise ProviderError(f"OpenAI {r.status_code}: {r.text[:300]}")
                msg = r.json()["choices"][0]["message"]
                msgs.append(msg)
                for tc in msg.get("tool_calls") or []:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    if name == "respond":
                        try:
                            return CopilotAnswer.model_validate(args), calls
                        except ValidationError as e:
                            out = {"error": f"Answer does not match the schema: {e}"}
                    else:
                        calls.append(ToolCall(name=name, args=args))
                        out = run_tool(ctx, name, args)
                    msgs.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(out, ensure_ascii=False, default=str)[:20000]})
        raise ProviderError("The model did not finish its answer within the step limit.")
