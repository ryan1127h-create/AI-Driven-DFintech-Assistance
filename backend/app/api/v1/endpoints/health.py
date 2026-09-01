from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness check."""
    return {"status": "ok"}
