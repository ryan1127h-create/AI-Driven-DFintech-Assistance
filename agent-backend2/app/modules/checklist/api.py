from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app.modules.auth.interface import get_current_user_id
from app.modules.checklist import service
from app.modules.checklist.schemas import ChecklistItemPatch, ChecklistResponse

router = APIRouter(prefix="/checklist")


@router.get("", response_model=ChecklistResponse)
async def get_checklist(user_id: str = Depends(get_current_user_id)):
    """Return the current user's checklist state."""
    try:
        return service.get_checklist(user_id)
    except Exception as exc:
        print(f"[checklist.api] Error: get_checklist failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to load checklist.") from exc


@router.patch("/items/{item_id}", response_model=ChecklistResponse)
async def patch_checklist_item(
    item_id: str, patch: ChecklistItemPatch, user_id: str = Depends(get_current_user_id)
):
    """Persist one checklist item update and return the full checklist."""
    fields = patch.model_dump(exclude_unset=True)
    try:
        return service.patch_checklist_item(item_id, fields, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"[checklist.api] Error: patch_checklist_item failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to update checklist item.") from exc


@router.post("/items/{item_id}/file", response_model=ChecklistResponse)
async def upload_checklist_item_file(
    item_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Upload one file for one checklist item and mark it completed."""
    try:
        return await service.upload_checklist_file(item_id, file, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"[checklist.api] Error: upload_checklist_file failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to upload the file.") from exc


@router.get("/items/{item_id}/file")
async def download_checklist_item_file(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Download the previously uploaded file for one checklist item, fetched
    back from Supabase Storage byte-for-byte identical to what was uploaded."""
    try:
        content, file_name, content_type = await service.download_checklist_file(item_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        print(f"[checklist.api] Error: download_checklist_file failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to download the file.") from exc

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
