from fastapi import APIRouter, File, HTTPException, UploadFile

from app.modules.checklist import service
from app.modules.checklist.schemas import ChecklistItemPatch, ChecklistResponse

router = APIRouter(prefix="/checklist")


@router.get("", response_model=ChecklistResponse)
async def get_checklist():
    """Return the current placeholder user's checklist state."""
    try:
        return service.get_checklist()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/items/{item_id}", response_model=ChecklistResponse)
async def patch_checklist_item(item_id: str, patch: ChecklistItemPatch):
    """Persist one checklist item update and return the full checklist."""
    fields = patch.model_dump(exclude_unset=True)
    try:
        return service.patch_checklist_item(item_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/items/{item_id}/file", response_model=ChecklistResponse)
async def upload_checklist_item_file(item_id: str, file: UploadFile = File(...)):
    """Upload one file for one checklist item and mark it completed."""
    try:
        return await service.upload_checklist_file(item_id, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
