from datetime import datetime, timezone

from app.core.errors import ForbiddenError
from app.core.errors import NotFoundError, ValidationError
from app.domains.admin import repository
from app.domains.auth import interface as auth_interface
from app.domains.knowledge_retrieval import interface as knowledge_interface

# Mirrors the check constraint on sis.applications.status.
APPLICATION_STATUSES = (
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED", "WAITLIST", "OFFER", "ACCEPTED", "REJECTED",
)
COURSE_STATUSES = ("active", "inactive")


def _require_admin(user_id: str) -> None:
    if not auth_interface.is_admin(user_id):
        raise ForbiddenError("Administrator access is required.")


def get_overview(user_id: str, days: int = 7) -> dict:
    _require_admin(user_id)
    return {"generated_at": datetime.now(timezone.utc), **repository.fetch_overview(days)}


def list_users(user_id: str, search: str = "") -> dict:
    _require_admin(user_id)
    return repository.list_users(search)


def get_user(user_id: str, target_user_id: str) -> dict:
    _require_admin(user_id)
    user = repository.get_user(target_user_id)
    if not user:
        raise NotFoundError("User not found.")
    return user


def update_user(user_id: str, target_user_id: str, changes: dict) -> dict:
    _require_admin(user_id)
    if changes.get("role") not in (None, "user", "admin"):
        raise ValidationError("Invalid account role.")
    if changes.get("account_status") not in (None, "active", "disabled"):
        raise ValidationError("Invalid account status.")
    if user_id == target_user_id and (
        changes.get("role") not in (None, "admin") or changes.get("account_status") not in (None, "active")
    ):
        raise ValidationError("An administrator cannot remove their own access.")
    if "full_name" in changes:
        # Through auth so Supabase's copy of the name stays in step.
        auth_interface.update_full_name(target_user_id, changes.pop("full_name"))
    user = repository.update_user(target_user_id, changes)
    if not user:
        raise NotFoundError("User not found.")
    return user


def delete_user(user_id: str, target_user_id: str) -> dict:
    _require_admin(user_id)
    if user_id == target_user_id:
        raise ValidationError("An administrator cannot delete their own account.")
    auth_interface.delete_account(target_user_id)
    return {"status": "deleted", "user_id": target_user_id}


def list_applications(user_id: str) -> dict:
    _require_admin(user_id)
    return repository.list_applications()


def list_escalations(user_id: str) -> dict:
    _require_admin(user_id)
    return repository.list_escalations()


def get_escalation(user_id: str, case_id: str) -> dict:
    _require_admin(user_id)
    result = repository.get_escalation(case_id)
    if not result:
        raise NotFoundError("Escalation case not found.")
    return result


def resolve_escalation(user_id: str, case_id: str) -> dict:
    _require_admin(user_id)
    result = repository.resolve_escalation(case_id, user_id)
    if not result:
        raise NotFoundError("Escalation case not found.")
    return result


def get_application(user_id: str, application_id: str) -> dict:
    _require_admin(user_id)
    result = repository.get_application(application_id)
    if not result: raise NotFoundError("Application not found.")
    return result


def update_application(user_id: str, application_id: str, changes: dict) -> dict:
    _require_admin(user_id)
    if "status" in changes and changes["status"] not in APPLICATION_STATUSES:
        raise ValidationError("Invalid application status.")
    if "final_decision" in changes:
        changes["final_decision"] = (changes["final_decision"] or "").strip() or None
    result = repository.update_application(application_id, changes, user_id)
    if not result: raise NotFoundError("Application not found.")
    return result


def update_checklist(user_id: str, item_id: str, submitted: bool) -> dict:
    _require_admin(user_id)
    result = repository.update_checklist_item(item_id, submitted)
    if not result: raise NotFoundError("Checklist item not found.")
    return result


def delete_application(user_id: str, application_id: str) -> dict:
    _require_admin(user_id)
    if not repository.delete_application(application_id): raise NotFoundError("Application not found.")
    return {"status": "deleted", "application_id": application_id}


def list_conversations(user_id: str) -> dict:
    _require_admin(user_id)
    return repository.list_conversations()


def get_conversation(user_id: str, conversation_id: str) -> dict:
    _require_admin(user_id)
    result = repository.get_conversation(conversation_id)
    if not result: raise NotFoundError("Conversation not found.")
    return result


def list_knowledge(user_id: str, search: str = "", main_table: str = "all") -> dict:
    _require_admin(user_id)
    return repository.list_knowledge(search, main_table)


def update_knowledge(user_id: str, item_id: str, category: str, changes: dict) -> dict:
    _require_admin(user_id)
    result = repository.update_knowledge(item_id, category, changes)
    if not result:
        raise NotFoundError("Knowledge item not found.")
    knowledge_interface.reload_catalogue()
    return result


def get_knowledge_course(user_id: str, course_code: str) -> dict:
    _require_admin(user_id)
    result = repository.get_knowledge_course(course_code)
    if not result:
        raise NotFoundError("Course not found.")
    return result


def update_knowledge_course(user_id: str, course_code: str, changes: dict) -> dict:
    _require_admin(user_id)
    if changes.get("status") not in (None, *COURSE_STATUSES):
        raise ValidationError("Invalid course status.")
    result = repository.update_knowledge_course(course_code, changes)
    if not result:
        raise NotFoundError("Course not found.")
    knowledge_interface.reload_catalogue()
    return result


def update_knowledge_course_related(user_id: str, course_code: str, relation: str, row: dict) -> dict:
    _require_admin(user_id)
    if relation not in repository.EDITABLE_COURSE_RELATIONS:
        raise ValidationError(f"Course {relation} can't be edited here.")
    result = repository.update_knowledge_course_related(course_code, relation, row)
    if not result:
        raise NotFoundError("Related course record not found.")
    knowledge_interface.reload_catalogue()
    return result
