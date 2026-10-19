from datetime import datetime, timezone

from app.core.errors import ForbiddenError
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domains.admin import repository
from app.domains.alumni import interface as alumni_interface
from app.domains.auth import interface as auth_interface
from app.domains.knowledge_retrieval import interface as knowledge_interface

logger = get_logger(__name__)

# Mirrors the check constraint on sis.applications.status.
APPLICATION_STATUSES = (
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED", "WAITLIST", "OFFER", "ACCEPTED", "REJECTED",
)
COURSE_STATUSES = ("active", "inactive")


def _require_admin(user_id: str) -> None:
    if not auth_interface.is_admin(user_id):
        raise ForbiddenError("Administrator access is required.")


# Display names for the classifier's intents and the agents' names.
_TOPIC_LABELS = {
    "admissions": "Admissions", "academic": "Academic", "financial": "Fees & Finance", "career": "Career Planning",
    "comparison": "Programme Comparison", "faq": "FAQ", "assessment": "Readiness Assessment",
    "course_recommendation": "Course Recommendation", "general": "General",
}
_AGENT_LABELS = {
    "admissions": "Admissions", "academic": "Academic", "financial": "Fees & Finance", "career": "Career Planning",
    "comparison": "Programme Comparison", "faq": "FAQ", "assessment": "Readiness Assessment",
    "course_recommendation": "Course Recommendation", "supervisor": "General Chat", "orchestrator": "Orchestrator",
}
_TOP_TOPICS = 5
# An agent is "Degraded" at or above either threshold.
_DEGRADED_FAILURE_RATE = 0.05
_DEGRADED_LATENCY_MS = 15_000


def _label(labels: dict, key: str) -> str:
    return labels.get(key) or key.replace("_", " ").title()


def _usage_view(usage: dict) -> dict:
    """{"available", "top_topics": {"all"|"applicant"|"enrolled_student": [{label, total}]},
    "agents": [{name, label, requests, success, failed, avg_latency_ms, status}]}."""
    groups: dict[str, dict[str, int]] = {"all": {}, "applicant": {}, "enrolled_student": {}}
    for row in usage["topics"]:
        for group in ("all", row["audience"]):
            if group in groups:
                groups[group][row["intent"]] = groups[group].get(row["intent"], 0) + row["total"]
    top_topics = {
        group: [{"label": _label(_TOPIC_LABELS, intent), "total": total}
                for intent, total in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:_TOP_TOPICS]]
        for group, counts in groups.items()
    }
    agents = []
    for row in usage["agents"]:
        degraded = (row["failed"] / row["requests"] >= _DEGRADED_FAILURE_RATE
                    or (row["avg_latency_ms"] or 0) >= _DEGRADED_LATENCY_MS)
        agents.append({
            "name": row["agent"], "label": _label(_AGENT_LABELS, row["agent"]), "requests": row["requests"],
            "success": row["requests"] - row["failed"], "failed": row["failed"],
            "avg_latency_ms": row["avg_latency_ms"], "status": "Degraded" if degraded else "Healthy",
        })
    return {"available": usage["available"], "top_topics": top_topics, "agents": agents}


def get_overview(user_id: str, days: int = 7) -> dict:
    _require_admin(user_id)
    overview = repository.fetch_overview(days)
    overview["usage"] = _usage_view(overview["usage"])
    return {"generated_at": datetime.now(timezone.utc), "days": days, **overview}


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
    if "account_status" in changes:
        # Through auth so disabling also revokes the user's current tokens.
        auth_interface.set_account_status(target_user_id, changes.pop("account_status"))
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


def resolve_escalation(user_id: str, case_id: str, notes: str | None = None) -> dict:
    _require_admin(user_id)
    result = repository.resolve_escalation(case_id, user_id, (notes or "").strip() or None)
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


# The chunk table and builder for each editable kind of knowledge row.
_CHUNK_SOURCES = {
    "admission_requirement": ("admissions_items", lambda src: knowledge_interface.chunk_builder.admission_item(src["row"])),
    "application_status": ("application_status_translations",
                           lambda src: knowledge_interface.chunk_builder.application_status(src["row"])),
    "courses": ("courses", lambda src: knowledge_interface.chunk_builder.course(src["row"], src["tags"], src["previous_metadata"])),
}
# Course relations whose text is part of the course's chunk.
_CHUNKED_COURSE_RELATIONS = {"description", "requirements"}


def _refresh_search_index(kind: str, source_id: str) -> str:
    """Rebuilds and re-embeds the retrieval chunk of an edited row, then
    drops the cached catalogue and retrievals. Returns "updated", "missing"
    (the row has no chunk to update) or "failed". A failure never undoes the
    edit itself: the row is saved, only the assistant's search text is stale,
    and the caller tells the admin so."""
    source_table, build = _CHUNK_SOURCES[kind]
    outcome = "failed"
    try:
        source = repository.fetch_chunk_source(source_table, source_id)
        if source is None:
            outcome = "missing"
        else:
            chunk = build(source)
            vector = knowledge_interface.embed_for_retrieval(chunk.embedding_text)
            outcome = "updated" if repository.store_chunk(chunk, vector) else "missing"
    except Exception:
        logger.exception("rebuilding the %s chunk of %s failed", source_table, source_id)
    knowledge_interface.reload_catalogue()
    return outcome


def update_knowledge(user_id: str, item_id: str, category: str, changes: dict) -> dict:
    _require_admin(user_id)
    result = repository.update_knowledge(item_id, category, changes)
    if not result:
        raise NotFoundError("Knowledge item not found.")
    return {**result, "search_index": _refresh_search_index(category, item_id)}


def get_knowledge_course(user_id: str, course_code: str) -> dict:
    _require_admin(user_id)
    result = repository.get_knowledge_course(course_code)
    if not result:
        raise NotFoundError("Course not found.")
    return result


def get_knowledge_program(user_id: str, program_id: str) -> dict:
    _require_admin(user_id)
    result = repository.get_knowledge_program(program_id)
    if not result:
        raise NotFoundError("Program not found.")
    return result


def update_knowledge_program(user_id: str, program_id: str, changes: dict) -> dict:
    _require_admin(user_id)
    result = repository.update_knowledge_program(program_id, changes)
    if not result:
        raise NotFoundError("Program not found.")
    return result


def update_knowledge_course(user_id: str, course_code: str, changes: dict) -> dict:
    _require_admin(user_id)
    if changes.get("status") not in (None, *COURSE_STATUSES):
        raise ValidationError("Invalid course status.")
    result = repository.update_knowledge_course(course_code, changes)
    if not result:
        raise NotFoundError("Course not found.")
    return {**result, "search_index": _refresh_search_index("courses", course_code)}


def update_knowledge_course_related(user_id: str, course_code: str, relation: str, row: dict) -> dict:
    _require_admin(user_id)
    if relation not in repository.EDITABLE_COURSE_RELATIONS:
        raise ValidationError(f"Course {relation} can't be edited here.")
    result = repository.update_knowledge_course_related(course_code, relation, row)
    if not result:
        raise NotFoundError("Related course record not found.")
    if relation in _CHUNKED_COURSE_RELATIONS:
        return {**result, "search_index": _refresh_search_index("courses", course_code)}
    knowledge_interface.reload_catalogue()
    return {**result, "search_index": "unchanged"}


# --- alumni directory (the alumni domain owns the data and its rules) -------

def list_alumni(user_id: str) -> dict:
    _require_admin(user_id)
    items = alumni_interface.staff_list()
    return {"items": items, "total": len(items), "expertise_options": alumni_interface.expertise_options()}


def create_alumnus(user_id: str, email: str, fields: dict) -> dict:
    _require_admin(user_id)
    return alumni_interface.staff_create(user_id, email, fields)


def update_alumnus(user_id: str, alumnus_id: str, fields: dict) -> dict:
    _require_admin(user_id)
    return alumni_interface.staff_update(alumnus_id, fields)


def delete_alumnus(user_id: str, alumnus_id: str) -> dict:
    _require_admin(user_id)
    alumni_interface.staff_delete(alumnus_id)
    return {"status": "deleted", "user_id": alumnus_id}
