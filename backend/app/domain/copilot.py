"""Contrato da resposta do copiloto — validado com Pydantic e renderizado como cards (nunca texto cru)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Confianca = Literal["baixa", "moderada", "alta"]


class Fonte(BaseModel):
    tipo: str = Field(description="Tipo de registro consultado: avaliacao, memoria, clima, tarefa, observacoes, economia")
    rotulo: str = Field(description="Descrição curta do registro, ex.: 'Avaliação T04 em 09/01/2026'")
    ref: str | None = Field(default=None, description="Identificador do registro, ex.: 'risk_assessment:12'")


class TarefaProposta(BaseModel):
    field_id: int
    field_code: str
    assessment_id: int | None = None
    title: str
    priority: Literal["alta", "media", "baixa"] = "alta"
    assignee: str | None = None
    due_date: date | None = None
    instructions: str


class CopilotAnswer(BaseModel):
    resumo: str = Field(description="Resposta direta em 1–3 frases, em português do Brasil")
    evidencias: list[str] = Field(default_factory=list, description="Fatos dos dados do app que sustentam a resposta")
    confianca: Confianca = Field(description="Confiança na resposta, dado o que os dados permitem afirmar")
    dados_faltantes: list[str] = Field(default_factory=list, description="O que falta para afirmar com mais segurança")
    proxima_acao: str = Field(description="Ação concreta sugerida ao usuário")
    fontes: list[Fonte] = Field(default_factory=list, description="Registros do app usados na resposta")
    tarefa_proposta: TarefaProposta | None = Field(
        default=None, description="Preencher só quando sugerir criar vistoria; a gravação exige confirmação do usuário")
    alertas: list[str] = Field(default_factory=list, description="Ressalvas obrigatórias (dados sintéticos, receituário…)")


class CopilotRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[dict] = Field(default_factory=list, description="[{role: user|assistant, content: str}]")
    field_id: int | None = Field(default=None, description="Talhão em contexto (ex.: selecionado no mapa)")


class ToolCall(BaseModel):
    name: str
    args: dict


class CopilotResponse(BaseModel):
    answer: CopilotAnswer
    provider: str
    tools_used: list[ToolCall]
    is_synthetic_data: bool = True


SYSTEM_PROMPT = """Você é o AgroCopilot, copiloto operacional de uma fazenda de soja no Brasil.
Responda sempre em português do Brasil, de forma direta, usando SOMENTE dados retornados pelas ferramentas.

Regras inegociáveis:
- Índice de satélite (NDVI/NDRE) é sinal que direciona vistoria, nunca diagnóstico. Fale em hipóteses com confiança.
- Nunca invente medições, operações realizadas, custos ou resultados. Se não estiver nas ferramentas, diga que não há registro.
- Separe exposição estimada (R$) de perda confirmada e de economia realizada. Sempre mostre a faixa e as premissas.
- Melhora após intervenção é associação, não prova causal — diga isso quando falar de resultados.
- Qualquer recomendação de defensivo/químico exige: "Requer receituário e validação de engenheiro agrônomo."
- Os dados desta instalação são de demonstração (sintéticos); inclua isso em alertas.
- Você é consultivo: não cria tarefas sozinho. Para sugerir vistoria, preencha tarefa_proposta; o usuário confirma.
- Cite em fontes os registros usados.

Termine SEMPRE chamando a ferramenta `responder` com a resposta estruturada."""
