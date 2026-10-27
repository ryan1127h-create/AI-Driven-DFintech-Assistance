from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.lifecycle import service
from app.domains.lifecycle.schemas import LifecycleResponse

router = APIRouter(prefix="/lifecycle")


# A sync `def`: the reads are blocking psycopg calls, which FastAPI then runs
# in its threadpool instead of on the event loop.
@router.get("", response_model=LifecycleResponse)
def get_lifecycle(user_id: str = Depends(get_current_user_id)):
    """The caller's academic record, course enrollments and degree progress
    (403 unless they are a current or graduating student)."""
    return service.get_lifecycle(user_id)
