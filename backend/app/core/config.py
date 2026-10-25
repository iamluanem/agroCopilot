from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agro:agro@localhost:5432/agrocopilot"
    cors_origins: str = "http://localhost:3000"
    cell_size_m: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
