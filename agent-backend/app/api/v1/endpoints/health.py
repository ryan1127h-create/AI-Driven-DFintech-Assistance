from fastapi import APIRouter

from app.clients.redis_client import ping as redis_ping
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness check, including session store backend status."""
    backend = settings.session_store_backend
    status = {"status": "ok", "phase": 2, "session_store": backend}
    if backend == "redis":
        status["redis_connected"] = redis_ping()
    return status
