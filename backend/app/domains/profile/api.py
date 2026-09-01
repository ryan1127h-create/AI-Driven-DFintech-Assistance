from fastapi import APIRouter, Depends

from app.core.errors import NotFoundError, ValidationError
from app.domains.auth.interface import get_current_user_id
from app.domains.profile import service
from app.domains.profile.schemas import ProfileOut, ProfilePatch

router = APIRouter(prefix="/profile")


@router.get("", response_model=ProfileOut)
async def get_profile(user_id: str = Depends(get_current_user_id)):
    """Return the current user's stored profile."""
    profile = service.get_profile(user_id)
    if profile is None:
        raise NotFoundError("No profile found. Upload a resume first.")
    return ProfileOut(user_id=user_id, **profile)


@router.patch("", response_model=ProfileOut)
async def patch_profile(patch: ProfilePatch, user_id: str = Depends(get_current_user_id)):
    """Apply user-confirmed corrections without clearing omitted fields."""
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise ValidationError("No profile fields provided.")

    profile = service.patch_profile(fields, user_id)
    if profile is None:
        raise NotFoundError("No profile found. Upload a resume first.")
    return ProfileOut(user_id=user_id, **profile)


@router.post("", response_model=ProfileOut)
async def create_profile(patch: ProfilePatch, user_id: str = Depends(get_current_user_id)):
    """Create or replace the profile submitted by the manual wizard."""
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        raise ValidationError("No profile fields provided.")

    profile = service.upsert_profile(fields, user_id)
    return ProfileOut(user_id=user_id, **profile)


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(user_id: str = Depends(get_current_user_id)):
    """
    Pulls the résumé already uploaded under the current user's "Curriculum
    vitae / CV" checklist item — this endpoint doesn't accept a direct file
    upload, so profile and checklist can never disagree about which résumé
    file is the current one. Extracts structured applicant facts with a
    single-purpose LLM agent (no intent classification, no conversation
    involved), and overwrites the stored profile for the current user.
    """
    profile = await service.generate_profile_from_uploaded_resume(user_id)
    return ProfileOut(user_id=user_id, **profile)
