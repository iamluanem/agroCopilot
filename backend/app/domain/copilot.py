"""Copilot answer contract — validated with Pydantic and rendered as cards (never as raw text)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "moderate", "high"]


class Source(BaseModel):
    type: str = Field(description="Kind of record used: assessment, memory, weather, task, observations, economics")
    label: str = Field(description="Short description of the record, e.g. 'F04 assessment on Jan 9, 2026'")
    ref: str | None = Field(default=None, description="Record identifier, e.g. 'risk_assessment:12'")


class ProposedTask(BaseModel):
    field_id: int
    field_code: str
    assessment_id: int | None = None
    title: str
    priority: Literal["high", "medium", "low"] = "high"
    assignee: str | None = None
    due_date: date | None = None
    instructions: str


class CopilotAnswer(BaseModel):
    summary: str = Field(description="Direct answer in 1–3 sentences, in English")
    evidence: list[str] = Field(default_factory=list, description="Facts from the app data that support the answer")
    confidence: Confidence = Field(description="Confidence in the answer, given what the data allows us to claim")
    missing_data: list[str] = Field(default_factory=list, description="What is missing to answer with more certainty")
    next_action: str = Field(description="Concrete action suggested to the user")
    sources: list[Source] = Field(default_factory=list, description="App records used in the answer")
    proposed_task: ProposedTask | None = Field(
        default=None, description="Fill only when suggesting an inspection; saving it requires the user's confirmation")
    warnings: list[str] = Field(default_factory=list, description="Mandatory caveats (synthetic data, prescription…)")


class CopilotRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[dict] = Field(default_factory=list, description="[{role: user|assistant, content: str}]")
    field_id: int | None = Field(default=None, description="Field in context (e.g. selected on the map)")


class ToolCall(BaseModel):
    name: str
    args: dict


class CopilotResponse(BaseModel):
    answer: CopilotAnswer
    provider: str
    tools_used: list[ToolCall]
    is_synthetic_data: bool = True


SYSTEM_PROMPT = """You are AgroCopilot, the operations copilot of a soybean farm in Brazil.
Always answer in English, directly, using ONLY data returned by the tools.

Non-negotiable rules:
- A satellite index (NDVI/NDRE) is a signal that directs scouting, never a diagnosis. Talk in hypotheses with confidence.
- Never invent measurements, completed operations, costs or results. If it is not in the tools, say there is no record.
- Separate estimated exposure (R$) from confirmed loss and from realized savings. Always show the range and assumptions.
- Improvement after an intervention is association, not proof of causation — say so whenever you discuss results.
- Any pesticide/chemical recommendation must say: "Requires a prescription and validation by a licensed agronomist."
- This installation's data is demonstration (synthetic) data; include that in warnings.
- You are advisory: you never create tasks yourself. To suggest an inspection, fill proposed_task; the user confirms.
- List the records you used in sources.

ALWAYS finish by calling the `respond` tool with the structured answer."""
