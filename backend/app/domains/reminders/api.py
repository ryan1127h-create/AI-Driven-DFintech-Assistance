from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.domains.auth.interface import get_current_user_id
from app.domains.reminders import service

router = APIRouter(prefix="/reminders")


class DismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=300)


@router.get("")
def list_reminders(user_id: str = Depends(get_current_user_id)):
    """The caller's open reminders, urgent first."""
    return {"items": service.list_reminders(user_id)}


@router.post("/dismiss", status_code=204)
def dismiss(body: DismissRequest, user_id: str = Depends(get_current_user_id)):
    """Hides one reminder until the situation it is about changes."""
    service.dismiss(user_id, body.key)
