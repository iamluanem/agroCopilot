import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.copilot_demo import DemoProvider
from app.application.copilot_tools import ToolContext
from app.domain.copilot import CopilotRequest, CopilotResponse
from app.infrastructure.db.models import AppSetting, Farm

SUGGESTIONS = [
    "Which fields need attention today?",
    "Why is Field 04 red?",
    "What is the estimated potential loss?",
    "Has this happened in this field before? What worked?",
    "How did the area evolve after the intervention?",
    "Create an inspection for F04",
]


def _choose(s: Session):
    """Order: LLM_PROVIDER (env) > Settings (app_settings) > auto (available key) > demo."""
    from app.infrastructure.llm.providers import AnthropicProvider, OpenAIProvider
    row = s.get(AppSetting, "llm_provider")
    env = os.getenv("LLM_PROVIDER", "auto")
    wanted = env if env != "auto" else ((row.value.get("value") if row else None) or "auto")
    available = {"anthropic": bool(os.getenv("ANTHROPIC_API_KEY")), "openai": bool(os.getenv("OPENAI_API_KEY"))}
    if wanted in ("auto", None):
        wanted = next((k for k, ok in available.items() if ok), "demo")
    if wanted == "anthropic" and available["anthropic"]:
        return AnthropicProvider()
    if wanted == "openai" and available["openai"]:
        return OpenAIProvider()
    return DemoProvider()


def status(s: Session) -> dict:
    p = _choose(s)
    return {"provider": p.name, "label": p.label, "suggestions": SUGGESTIONS,
            "available": {"demo": True, "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
                          "openai": bool(os.getenv("OPENAI_API_KEY"))}}


def ask(s: Session, req: CopilotRequest) -> CopilotResponse:
    farm = s.scalars(select(Farm).order_by(Farm.id)).first()
    if not farm:
        raise LookupError("No farm registered")
    ctx = ToolContext(s=s, farm=farm)
    provider = _choose(s)
    try:
        answer, calls = provider.answer(req, ctx)
        name = provider.label
    except Exception as e:  # an LLM failure never breaks the copilot: fall back to deterministic mode
        demo = DemoProvider()
        answer, calls = demo.answer(req, ctx)
        answer.warnings.insert(0, f"{provider.label} unavailable ({str(e)[:120]}). Answer generated in demo mode.")
        name = demo.label
    if not any("synthetic" in a.lower() for a in answer.warnings):
        answer.warnings.append("Demo data (synthetic).")
    return CopilotResponse(answer=answer, provider=name, tools_used=calls)
