from fastapi import APIRouter, File, HTTPException, UploadFile

from app.modules.profile import service
from app.modules.profile.constants import TEST_USER_ID
from app.modules.profile.schemas import ProfileOut, ProfilePatch

router = APIRouter(prefix="/profile")

_SUPPORTED_SUFFIXES = (".pdf", ".docx")


@router.get("", response_model=ProfileOut)
async def get_profile():
    """Return the current placeholder user's stored profile."""
    try:
        profile = service.get_profile()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Upload a resume first.",
        )
    return ProfileOut(user_id=TEST_USER_ID, **profile)


@router.patch("", response_model=ProfileOut)
async def patch_profile(patch: ProfilePatch):
    """Apply user-confirmed corrections without clearing omitted fields."""
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No profile fields provided.")

    try:
        profile = service.patch_profile(fields)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Upload a resume first.",
        )
    return ProfileOut(user_id=TEST_USER_ID, **profile)


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
