from fastapi import APIRouter, Depends, HTTPException

from app.modules.auth.interface import get_current_user_id
from app.modules.checklist import interface as checklist_interface
from app.modules.profile import service
from app.modules.profile.agents.resume_parser import SUPPORTED_EXTENSIONS
from app.modules.profile.schemas import ProfileOut, ProfilePatch

router = APIRouter(prefix="/profile")

_SUPPORTED_SUFFIXES = tuple(f".{ext}" for ext in SUPPORTED_EXTENSIONS)


@router.get("", response_model=ProfileOut)
async def get_profile(user_id: str = Depends(get_current_user_id)):
    """Return the current user's stored profile."""
    try:
        profile = service.get_profile(user_id)
    except Exception as exc:
        print(f"[profile.api] Error: get_profile failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to load profile.") from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Upload a resume first.",
        )
    return ProfileOut(user_id=user_id, **profile)


@router.patch("", response_model=ProfileOut)
async def patch_profile(patch: ProfilePatch, user_id: str = Depends(get_current_user_id)):
    """Apply user-confirmed corrections without clearing omitted fields."""
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No profile fields provided.")

    try:
        profile = service.patch_profile(fields, user_id)
    except Exception as exc:
        print(f"[profile.api] Error: patch_profile failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to update profile.") from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Upload a resume first.",
        )
    return ProfileOut(user_id=user_id, **profile)


@router.post("", response_model=ProfileOut)
async def create_profile(patch: ProfilePatch, user_id: str = Depends(get_current_user_id)):
    """Create or replace the profile submitted by the manual wizard."""
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No profile fields provided.")

    try:
        profile = service.upsert_profile(fields, user_id)
    except Exception as exc:
        print(f"[profile.api] Error: create_profile failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to save profile.") from exc

    return ProfileOut(user_id=user_id, **profile)


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(user_id: str = Depends(get_current_user_id)):
    """
    Pulls the resume already uploaded under the current user's "Curriculum
    vitae / CV" checklist item (see app/modules/checklist/interface.py) —
    this endpoint no longer accepts a direct file upload, so profile and
    checklist can never disagree about which résumé file is the current one.
    Extracts structured applicant facts with a single-purpose LLM agent
    (app/modules/profile/agents/resume_agent.py — no intent classification,
    no conversation involved), and overwrites the stored profile for the
    current user.
    """
    uploaded = await checklist_interface.get_uploaded_file(checklist_interface.RESUME_ITEM_ID, user_id)
    if uploaded is None:
        raise HTTPException(
            status_code=404,
            detail="No resume found in your checklist yet. Please upload your CV "
                   "under the checklist first.",
        )
    content, file_name, _content_type = uploaded

    if not file_name or not file_name.lower().endswith(_SUPPORTED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Only {_SUPPORTED_SUFFIXES} resumes are supported, but the file "
                   f"uploaded under the checklist CV item is '{file_name}'. Please "
                   "re-upload your CV there in a supported format.",
        )

    try:
        profile = service.generate_profile_from_resume(content, file_name, user_id)
        return ProfileOut(user_id=user_id, **profile)
    except ValueError as exc:
        # e.g. "Could not extract any text from the uploaded resume." — a
        # client-fixable problem with the uploaded file, not a server error.
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"[profile.api] Error: generate_profile_from_resume failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to process the uploaded resume.") from exc
