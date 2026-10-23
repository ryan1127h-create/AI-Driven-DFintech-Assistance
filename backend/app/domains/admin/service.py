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
    "course_recommendation": "Course Recommendation", "alumni": "Alumni Match", "general": "General",
}
_AGENT_LABELS = {
    "admissions": "Admissions", "academic": "Academic", "financial": "Fees & Finance", "career": "Career Planning",
    "comparison": "Programme Comparison", "faq": "FAQ", "assessment": "Readiness Assessment",
    "course_recommendation": "Course Recommendation", "alumni": "Alumni Match", "supervisor": "General Chat",
    "orchestrator": "Orchestrator",
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



# The policy stages in the order a student moves through them (app/core/stage_policy.py).
_STAGE_LABELS = {
    "prospect": "Prospective students", "applicant": "Applicants", "rejected": "Not admitted",
    "admitted": "Admitted", "current": "Current students", "graduating": "Graduating", "alumni": "Alumni",
}
_SUB_STAGE_LABELS = {
    "browsing": "Browsing", "comparing": "Comparing", "decided_to_apply": "Decided to apply", "DRAFT": "Draft",
    "SUBMITTED": "Submitted", "UNDER_REVIEW": "Under review", "DOCS_REQUIRED": "Documents required",
    "WAITLIST": "Waitlisted", "OFFER": "Offer", "ACCEPTED": "Accepted",
}
_TOPICS_PER_STAGE = 3


def _stage_order(stage: str) -> int:
    return list(_STAGE_LABELS).index(stage) if stage in _STAGE_LABELS else len(_STAGE_LABELS)


def _insights_view(raw: dict) -> dict:
    """The staff insights: the share of questions answered without a person,
    questions per stage with their commonest topics, the latest questions the
    assistant couldn't answer, the student funnel, and alumni use."""
    turns = raw["resolution"]["turns"]
    unresolved = raw["resolution"]["unresolved_turns"] + raw["resolution"]["escalated"]
    resolution = {
        "turns": turns, "unresolved_turns": raw["resolution"]["unresolved_turns"],
        "escalated": raw["resolution"]["escalated"],
        "rate": round(max(turns - unresolved, 0) / turns, 3) if turns else None,
    }

    topics: dict[str, list] = {}
    for row in sorted(raw["stage_topics"], key=lambda row: (-row["total"], row["intent"])):
        topics.setdefault(row["stage"], []).append({"label": _label(_TOPIC_LABELS, row["intent"]), "total": row["total"]})
    stages = [
        {"stage": row["stage"], "label": _label(_STAGE_LABELS, row["stage"]), "questions": row["total"],
         "top_topics": topics.get(row["stage"], [])[:_TOPICS_PER_STAGE]}
        for row in sorted(raw["stage_turns"], key=lambda row: _stage_order(row["stage"]))
    ]

    gaps = [
        {"created_at": row["created_at"], "stage": _label(_STAGE_LABELS, row["stage"]),
         "topics": [_label(_TOPIC_LABELS, intent) for intent in row["intents"] if intent != "off_topic"],
         "agents": [_label(_AGENT_LABELS, agent) for agent in row["failed_agents"]],
         "outcome": row["outcome"], "conversation_id": row["conversation_id"], "case_summary": row["case_summary"]}
        for row in raw["gaps"]
    ]

    # Applicants turned down sit under "applicant"; the funnel shows them apart.
    funnel: dict[str, dict] = {}
    for row in raw["funnel"]:
        stage = "rejected" if row["stage"] == "applicant" and row["sub_stage"] == "REJECTED" else row["stage"]
        step = funnel.setdefault(stage, {"stage": stage, "label": _label(_STAGE_LABELS, stage), "total": 0, "breakdown": []})
        step["total"] += row["total"]
        if stage != "rejected" and row["sub_stage"] in _SUB_STAGE_LABELS:
            step["breakdown"].append({"label": _SUB_STAGE_LABELS[row["sub_stage"]], "total": row["total"]})
    for step in funnel.values():
        step["breakdown"].sort(key=lambda part: -part["total"])

    requests = {row["status"]: row["total"] for row in raw["alumni"]["requests"]}
    answered = requests.get("accepted", 0) + requests.get("declined", 0)
    alumni = {
        "questions": raw["alumni"]["questions"],
        "requests": sum(requests.values()), "pending": requests.get("pending", 0),
        "accepted": requests.get("accepted", 0), "declined": requests.get("declined", 0),
        "acceptance_rate": round(requests.get("accepted", 0) / answered, 3) if answered else None,
        **raw["alumni"]["sharing"],
    }
    return {
        "available": True, "resolution": resolution, "stages": stages, "gaps": gaps,
        "funnel": sorted(funnel.values(), key=lambda step: _stage_order(step["stage"])), "alumni": alumni,
    }


def get_insights(user_id: str, days: int = 30) -> dict:
    _require_admin(user_id)
    raw = repository.fetch_insights(days)
    view = _insights_view(raw) if raw["available"] else {"available": False}
    return {"generated_at": datetime.now(timezone.utc), "days": days, **view}


# The stages the user list can be narrowed to ("staff": admins).
USER_STAGES = ("prospect", "applicant", "admitted", "current", "graduating", "alumni", "staff")


def list_users(user_id: str, search: str = "", stage: str = "") -> dict:
    _require_admin(user_id)
    if stage and stage not in USER_STAGES:
        raise ValidationError(f"Unknown stage: {stage}")
    return repository.list_users(search, stage)


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
