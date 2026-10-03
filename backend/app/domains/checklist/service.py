"""
Checklist service — the user's admission application as the school records
it (schema sis): status, overview, and which admissions documents the
school has received. Read-only; documents are submitted through the
university's own application system, never uploaded here.

Before an application is linked the checklist is empty: a prospect links
theirs by application number (bind_application), which also moves them
from prospect to applicant.
"""

from __future__ import annotations

from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationError
from app.core.logging import get_logger
from app.domains.auth import interface as auth_interface
from app.domains.checklist.schemas import ChecklistResponse
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.profile import interface as profile_interface
from app.domains.sis import interface as sis

logger = get_logger(__name__)


def _describe_application(application: dict) -> dict:
    """Adds the status explanation and each document's label, description
    and required flag; required documents first."""
    items = knowledge.list_admissions_items()
    documents = [
        {**items.get(d["item_key"], {"label": None, "description": None, "required": False}), **d}
        for d in application["documents"]
    ]
    documents.sort(key=lambda d: (not d["required"], d["label"] or d["item_key"]))
    return {**application, **knowledge.explain_application_status(application["status"]), "documents": documents}


def get_checklist(user_id: str) -> ChecklistResponse:
    """The user's stage and their most recent application, if any."""
    applications = sis.list_applications(user_id)
    return ChecklistResponse(
        user_id=user_id,
        lifecycle_stage=profile_interface.get_profile_field(user_id, "lifecycle_stage"),
        application=_describe_application(applications[0]) if applications else None,
    )


def bind_application(user_id: str, application_no: str) -> ChecklistResponse:
    """Claims the application filed under the user's login email with this
    application number, and moves the user from prospect to applicant.
    Only prospects can bind (other stage changes aren't supported yet)."""
    application_no = application_no.strip()
    if not application_no:
        raise ValidationError("Application number is required.")
    stage = profile_interface.get_profile_field(user_id, "lifecycle_stage")
    if stage not in (None, "prospect"):
        raise ValidationError("An application can only be bound before you have one on file.")
    email = auth_interface.get_login_email(user_id)
    if email is None:
        raise NotFoundError("Account not found.")

    application_id = sis.bind_application(user_id, application_no, email)
    if application_id is None:
        raise ValidationError(
            "No unclaimed application matches this application number and your login email."
        )
    try:
        profile_interface.set_lifecycle_stage(user_id, "applicant", source="DB", actor=f"user:{user_id}")
    except Exception as exc:
        # Keep sis and the profile consistent: an application bound to a
        # user who is still a prospect would hide its status (sub_stage).
        logger.error("binding %s for %s: stage update failed, unbinding: %s", application_no, user_id, exc)
        sis.unbind_application(user_id, application_id)
        raise ServiceUnavailableError("Couldn't bind the application right now. Please try again.") from exc
    return get_checklist(user_id)
