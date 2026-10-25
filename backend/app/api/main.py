from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routers import farms
from app.core.config import get_settings

app = FastAPI(
    title="AgroCopilot API",
    version="0.1.0",
    description="Copiloto operacional da fazenda — MVP. Dados sintéticos são marcados com `is_synthetic`.",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(farms.router)


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
