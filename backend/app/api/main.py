import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import copilot, farms, imagery, intelligence, settings, tasks
from app.application.intelligence import warm_cache
from app.application.operations import MEDIA_DIR
from app.core.config import get_settings



@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_warm, daemon=True).start()
    yield


def _warm() -> None:
    try:
        warm_cache()
    except Exception as e:  # caching is an optimization; it never takes the API down
        print(f"[warm_cache] ignorado: {e}")


app = FastAPI(
    lifespan=lifespan,
    title="AgroCopilot API",
    version="0.1.0",
    description="Farm operations copilot — MVP. Synthetic data is flagged with `is_synthetic`.",
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
app.include_router(settings.router)
app.include_router(imagery.router)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
