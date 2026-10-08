"""
FastAPI entrypoint. Wires together the cross-cutting kernel (structured
logging, the shared error-handler taxonomy), CORS, and every domain
mounted so far — see app/api/v1/router.py for the full list.
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging, get_logger
from app.domains.derived_labels.service import register as register_derived_labels
from app.domains.knowledge_retrieval.interface import warm_cache
from app.tools.registration import register_all as register_tools

configure_logging()
register_tools()
register_derived_labels()

logger = get_logger(__name__)


def _warm_knowledge_cache() -> None:
    try:
        warm_cache()
    except Exception:
        logger.exception("warming the knowledge cache failed; the first request will load it")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In the background, so a slow or unreachable database never holds up startup.
    threading.Thread(target=_warm_knowledge_cache, name="knowledge-cache-warmup", daemon=True).start()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Agentic AI assistant for NUS MSc DFT",
    version="0.1.0",
    lifespan=lifespan,
)

register_error_handlers(app)
app.add_middleware(CorrelationIdMiddleware)

_cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
async def root():
    return {"app": settings.app_name, "status": "running", "docs": "/docs"}
