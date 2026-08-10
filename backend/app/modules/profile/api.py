from fastapi import APIRouter, File, HTTPException, UploadFile

from app.modules.profile import service
from app.modules.profile.constants import TEST_USER_ID
from app.modules.profile.schemas import ProfileOut

router = APIRouter(prefix="/profile")

_SUPPORTED_SUFFIXES = (".pdf", ".docx")


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(file: UploadFile = File(...)):
    """
    Uploads a resume (PDF or DOCX), extracts structured applicant facts with
    a single-purpose LLM agent (app/modules/profile/agent.py — no intent
    classification, no conversation involved), and overwrites the stored
    profile for the current placeholder user (see
    app/modules/profile/constants.py::TEST_USER_ID).
    """
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Only {_SUPPORTED_SUFFIXES} resumes are supported.",
        )

    try:
        content = await file.read()
        profile = service.generate_profile_from_resume(content, file.filename)
        return ProfileOut(user_id=TEST_USER_ID, **profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
