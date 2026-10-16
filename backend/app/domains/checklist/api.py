from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.checklist import service
from app.domains.checklist.schemas import BindApplicationRequest, ChecklistResponse

router = APIRouter(prefix="/checklist")


@router.get("", response_model=ChecklistResponse)
def get_checklist(user_id: str = Depends(get_current_user_id)):
    """The caller's application and the documents the school has received
    (no application yet: application is null)."""
    return service.get_checklist(user_id)


@router.post("/application", response_model=ChecklistResponse)
def bind_application(request: BindApplicationRequest, user_id: str = Depends(get_current_user_id)):
    """Binds the admission application filed under the caller's login email
    to their account; afterwards the checklist shows its status and the
    school's record of received documents."""
    return service.bind_application(user_id, request.application_no)
