from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.profile import service
from app.domains.profile.schemas import (
    ConflictOut,
    ConflictResolution,
    ConsentOut,
    ConsentUpdate,
    DefinitionsOut,
    ProfileOut,
    ProfileUpdate,
)

router = APIRouter(prefix="/profile")


@router.get("", response_model=ProfileOut)
async def get_profile(user_id: str = Depends(get_current_user_id)):
    """The current user's profile: every displayed field on file, with its
    source and whether the user may edit it. Always 200 — a new account
    simply has few fields."""
    return service.get_profile(user_id)


@router.get("/definitions", response_model=DefinitionsOut)
async def get_definitions(user_id: str = Depends(get_current_user_id)):
    """The field dictionary the profile form is built from."""
    return service.get_definitions()


@router.patch("", response_model=ProfileOut)
async def update_profile(update: ProfileUpdate, user_id: str = Depends(get_current_user_id)):
    """Sets (or, with null, deletes) several fields at once — all or none."""
    cv_document_id = str(update.cv_document_id) if update.cv_document_id else None
    return service.update_fields(user_id, update.fields, cv_document_id)


@router.get("/conflicts", response_model=list[ConflictOut])
async def list_conflicts(user_id: str = Depends(get_current_user_id)):
    return service.list_conflicts(user_id)


@router.post("/conflicts/{conflict_id}", response_model=ProfileOut)
async def resolve_conflict(
    conflict_id: int, resolution: ConflictResolution, user_id: str = Depends(get_current_user_id)
):
    return service.resolve_conflict(user_id, conflict_id, resolution.action)


@router.get("/consents", response_model=list[ConsentOut])
async def get_consents(user_id: str = Depends(get_current_user_id)):
    return service.get_consents(user_id)


@router.put("/consents", response_model=list[ConsentOut])
async def update_consents(update: ConsentUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_consents(user_id, update.consents)

