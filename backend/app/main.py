from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Agentic AI assistant for NUS MSc DFT ",
    version="0.1.0",
)

# CORS — open for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "phase": 2,
        "status": "running",
        "docs": "/docs",
    }
