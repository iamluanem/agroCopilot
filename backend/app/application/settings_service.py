"""Configurações editáveis: premissas econômicas, limiares de risco e provedor do copiloto."""
import threading
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.application import map_service
from app.infrastructure.db.models import AppSetting


class Economia(BaseModel):
    produtividade_esperada_sc_ha: float = Field(ge=10, le=120)
    preco_saca_rs: float = Field(ge=30, le=400)
    perda_min_pct: float = Field(ge=0, le=100)
    perda_max_pct: float = Field(ge=0, le=100)
    custo_vistoria_rs: float = Field(ge=0, le=100_000)
    custo_intervencao_rs_ha: float = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def _range(self):
        if self.perda_min_pct > self.perda_max_pct:
            raise ValueError("A perda mínima não pode ser maior que a máxima")
        return self


class Risco(BaseModel):
    limiar_amarelo: float = Field(ge=0.5, le=5)
    limiar_vermelho: float = Field(ge=1, le=8)
    peso_historico: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _order(self):
        if self.limiar_vermelho <= self.limiar_amarelo:
            raise ValueError("O limiar crítico precisa ser maior que o de atenção")
        return self


class SettingsIn(BaseModel):
    economia: Economia
    risco: Risco
    llm_provider: Literal["auto", "demo", "anthropic", "openai"] = "auto"


def get_settings(s: Session) -> dict:
    from app.application.copilot_service import status
    rows = {r.key: r.value for r in s.query(AppSetting)}
    return dict(economia=rows.get("economia"), risco=rows.get("risco"),
                llm_provider=(rows.get("llm_provider") or {}).get("valor", "auto"),
                copilot=status(s), seed_version=(rows.get("seed_version") or {}).get("valor"))


def _warm():
    try:
        from app.application.intelligence import warm_cache
        warm_cache()
    except Exception as e:  # pré-cálculo é otimização
        print(f"[settings] warm_cache ignorado: {e}")


def save_settings(s: Session, data: SettingsIn) -> dict:
    s.merge(AppSetting(key="economia", value=data.economia.model_dump()))
    s.merge(AppSetting(key="risco", value=data.risco.model_dump()))
    s.merge(AppSetting(key="llm_provider", value={"valor": data.llm_provider}))
    s.commit()
    map_service.clear_cache()
    threading.Thread(target=_warm, daemon=True).start()
    return get_settings(s)
