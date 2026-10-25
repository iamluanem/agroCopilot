import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.copilot_demo import DemoProvider
from app.application.copilot_tools import ToolContext
from app.domain.copilot import CopilotRequest, CopilotResponse
from app.infrastructure.db.models import AppSetting, Farm

SUGGESTIONS = [
    "Quais talhões precisam de atenção hoje?",
    "Por que o Talhão 04 está vermelho?",
    "Qual é a perda potencial estimada?",
    "Isso já aconteceu nesse talhão? O que funcionou?",
    "Como a área evoluiu depois da intervenção?",
    "Crie uma vistoria para o T04",
]


def _choose(s: Session):
    """Ordem: LLM_PROVIDER (env) > Configurações (app_settings) > auto (chave disponível) > demo."""
    from app.infrastructure.llm.providers import AnthropicProvider, OpenAIProvider
    row = s.get(AppSetting, "llm_provider")
    env = os.getenv("LLM_PROVIDER", "auto")
    wanted = env if env != "auto" else ((row.value.get("valor") if row else None) or "auto")
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
        raise LookupError("Nenhuma fazenda cadastrada")
    ctx = ToolContext(s=s, farm=farm)
    provider = _choose(s)
    try:
        answer, calls = provider.answer(req, ctx)
        name = provider.label
    except Exception as e:  # falha do LLM não derruba o copiloto: cai para o modo determinístico
        demo = DemoProvider()
        answer, calls = demo.answer(req, ctx)
        answer.alertas.insert(0, f"{provider.label} indisponível ({str(e)[:120]}). Resposta gerada pelo modo demo.")
        name = demo.label
    if not any("sintétic" in a for a in answer.alertas):
        answer.alertas.append("Dados de demonstração (sintéticos).")
    return CopilotResponse(answer=answer, provider=name, tools_used=calls)
