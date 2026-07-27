from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.api.chat import router as chat_router
from student.api2 import router as student_router


BASE_DIR = Path(__file__).resolve().parents[1]   # goes to backend/
UPLOAD_DIR = BASE_DIR / "uploads"

# ✅ ensure folder exists
UPLOAD_DIR.mkdir(exist_ok=True)

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

app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(student_router, prefix="/api", tags=["application"])

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "phase": 2,
        "status": "running",
        "docs": "/docs",
    }