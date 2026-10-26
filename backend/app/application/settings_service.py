"""Editable settings: economic assumptions, risk thresholds and copilot provider."""
import threading
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.application import map_service
from app.infrastructure.db.models import AppSetting


class Economics(BaseModel):
    expected_yield_bags_ha: float = Field(ge=10, le=120)
    bag_price_brl: float = Field(ge=30, le=400)
    loss_min_pct: float = Field(ge=0, le=100)
    loss_max_pct: float = Field(ge=0, le=100)
    inspection_cost_brl: float = Field(ge=0, le=100_000)
    intervention_cost_brl_ha: float = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def _range(self):
        if self.loss_min_pct > self.loss_max_pct:
            raise ValueError("Minimum loss cannot be greater than maximum loss")
        return self


class Risk(BaseModel):
    yellow_threshold: float = Field(ge=0.5, le=5)
    red_threshold: float = Field(ge=1, le=8)
    history_weight: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _order(self):
        if self.red_threshold <= self.yellow_threshold:
            raise ValueError("The critical threshold must be greater than the watch threshold")
        return self


class SettingsIn(BaseModel):
    economics: Economics
    risk: Risk
    llm_provider: Literal["auto", "demo", "anthropic", "openai"] = "auto"


def get_settings(s: Session) -> dict:
    from app.application.copilot_service import status
    rows = {r.key: r.value for r in s.query(AppSetting)}
    return dict(economics=rows.get("economics"), risk=rows.get("risk"),
                llm_provider=(rows.get("llm_provider") or {}).get("value", "auto"),
                copilot=status(s), seed_version=(rows.get("seed_version") or {}).get("value"))


def _warm():
    try:
        from app.application.intelligence import warm_cache
        warm_cache()
    except Exception as e:  # precomputation is an optimization
        print(f"[settings] warm_cache skipped: {e}")


def save_settings(s: Session, data: SettingsIn) -> dict:
    s.merge(AppSetting(key="economics", value=data.economics.model_dump()))
    s.merge(AppSetting(key="risk", value=data.risk.model_dump()))
    s.merge(AppSetting(key="llm_provider", value={"value": data.llm_provider}))
    s.commit()
    map_service.clear_cache()
    threading.Thread(target=_warm, daemon=True).start()
    return get_settings(s)
