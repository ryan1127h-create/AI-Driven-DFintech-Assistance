"""
FastAPI entrypoint. Wires together the cross-cutting kernel (structured
logging, the shared error-handler taxonomy), CORS, and every domain
mounted so far — see app/api/v1/router.py for the full list.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.tools.registration import register_all as register_tools

configure_logging()
register_tools()

app = FastAPI(
    title=settings.app_name,
    description="Agentic AI assistant for NUS MSc DFT",
    version="0.1.0",
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
