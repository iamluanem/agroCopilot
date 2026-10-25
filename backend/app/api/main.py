import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routers import copilot, farms, intelligence, tasks
from app.application.intelligence import warm_cache
from app.core.config import get_settings



@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_warm, daemon=True).start()
    yield


def _warm() -> None:
    try:
        warm_cache()
    except Exception as e:  # cache é otimização; nunca derruba a API
        print(f"[warm_cache] ignorado: {e}")


app = FastAPI(
    lifespan=lifespan,
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
app.include_router(intelligence.router)
app.include_router(copilot.router)
app.include_router(tasks.router)


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
