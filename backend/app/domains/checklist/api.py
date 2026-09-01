from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.domains.auth.interface import get_current_user_id
from app.domains.checklist import service
from app.domains.checklist.schemas import ChecklistItemPatch, ChecklistResponse

router = APIRouter(prefix="/checklist")


@router.get("", response_model=ChecklistResponse)
async def get_checklist(user_id: str = Depends(get_current_user_id)):
    """Return the current user's checklist state."""
    return service.get_checklist(user_id)


@router.patch("/items/{item_id}", response_model=ChecklistResponse)
async def patch_checklist_item(item_id: str, patch: ChecklistItemPatch, user_id: str = Depends(get_current_user_id)):
    """Persist one checklist item update and return the full checklist."""
    fields = patch.model_dump(exclude_unset=True)
    return service.patch_checklist_item(item_id, fields, user_id=user_id)


@router.post("/items/{item_id}/file", response_model=ChecklistResponse)
async def upload_checklist_item_file(
    item_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Upload one file for one checklist item and mark it completed."""
    return await service.upload_checklist_file(item_id, file, user_id=user_id)


@router.get("/items/{item_id}/file")
async def download_checklist_item_file(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Download the previously uploaded file for one checklist item, fetched
    back from object storage byte-for-byte identical to what was uploaded."""
    content, file_name, content_type = await service.download_checklist_file(item_id, user_id=user_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
