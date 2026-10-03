from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile

from app.domains.auth.interface import get_current_user_id
from app.domains.cv_import import service
from app.domains.cv_import.schemas import CvImportOut

router = APIRouter(prefix="/cv-import")


# Sync `def`s: text extraction, the LLM call and the psycopg writes all
# block, so FastAPI runs these in its threadpool.
@router.post("", response_model=CvImportOut)
def import_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    """Reads a PDF or DOCX CV (5 MB at most) into checked profile
    candidates. The file isn't stored. Needs the CV-processing consent
    (403 without it); at most 3 uploads an hour (429)."""
    data = file.file.read(service.MAX_FILE_BYTES + 1)
    return service.import_cv(user_id, file.filename or "", data)


@router.get("/latest", response_model=Optional[CvImportOut])
def latest_import(user_id: str = Depends(get_current_user_id)):
    """The caller's most recent CV import, or null."""
    return service.latest_import(user_id)


@router.delete("")
def delete_cv_data(user_id: str = Depends(get_current_user_id)):
    """Forgets what was kept from the caller's CVs (extracted details and
    the quotes behind them). Values already on the profile stay."""
    return service.delete_cv_data(user_id)
