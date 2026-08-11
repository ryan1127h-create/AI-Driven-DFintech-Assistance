from fastapi import APIRouter, HTTPException

from app.modules.checklist import service
from app.modules.checklist.schemas import ChecklistItemPatch, ChecklistResponse

router = APIRouter(prefix="/checklist")


@router.get("", response_model=ChecklistResponse)
async def get_checklist():
    """Return the current checklist API contract payload."""
    try:
        return service.get_checklist()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/items/{item_id}", response_model=ChecklistResponse)
async def patch_checklist_item(item_id: str, patch: ChecklistItemPatch):
    """Future endpoint for persisted checklist item updates."""
    _ = (item_id, patch)
    raise HTTPException(
        status_code=501,
        detail="Checklist item persistence is not implemented yet.",
    )

