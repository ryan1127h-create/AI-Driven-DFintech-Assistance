"""
Gathers each rule's inputs through the owning domains' interfaces, runs the
rules, and stores the labels on the profile. register() hooks the
recomputation onto profile changes and returning users (app.core.events).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.core import events
from app.core.logging import get_logger
from app.domains.derived_labels import rules
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.profile import interface as profile_interface
from app.domains.sis import interface as sis
from app.domains.specialist.course_recommendation import interface as course_recommendation

logger = get_logger(__name__)

# A returning user's labels are only recomputed when older than this
# (time is an input to drop-off and graduation risk).
REFRESH_AFTER = timedelta(hours=12)
_STUDY_STAGES = {"CUR", "GRD"}


def _catalogue() -> list[dict]:
    electives = knowledge.list_course_electives()
    return [
        {"code": row["course_code"], "units": int(row["module_credit"] or 0), "vertical": electives.get(row["course_code"], [])}
        for row in knowledge.list_courses()
    ]


def _graduation_risk(user_id: str, values: dict, today: date) -> list[dict]:
    enrollments = sis.list_enrollments(user_id)
    codes = lambda status: [e["course_code"] for e in enrollments if e["status"] == status]  # noqa: E731
    completed, current, planned = codes("completed"), codes("current"), codes("planned")
    catalogue = _catalogue()
    return rules.graduation_risk_flags(
        values,
        completed_progress=course_recommendation.compute_degree_progress(catalogue, completed),
        projected_progress=course_recommendation.compute_degree_progress(catalogue, completed + current),
        planned_progress=course_recommendation.compute_degree_progress(catalogue, completed + current + planned),
        current_units=float(sum(e["credits"] or 0 for e in enrollments if e["status"] == "current")),
        current_codes=set(current),
        planned_codes=set(planned),
        today=today,
    )


def _drop_off_risk(user_id: str, values: dict, today: date) -> str | None:
    applications = sis.list_applications(user_id)
    required = {key for key, item in knowledge.list_admissions_items().items() if item["required"]}
    return rules.drop_off_risk(applications[0] if applications else None, required, values, today)


def compute_labels(user_id: str, today: date | None = None) -> dict:
    """The labels for one user, without storing them."""
    today = today or date.today()
    values = profile_interface.get_profile_values(user_id)
    stage_code = rules.STAGE_CODES.get(values.get("lifecycle_stage"))
    return {
        "profile_usability": rules.profile_usability(values, profile_interface.field_definitions(), stage_code),
        "motivation_segment": rules.motivation_segment(values),
        "readiness_gap": rules.readiness_gap(values) if stage_code in rules.READINESS_STAGES else None,
        "drop_off_risk": _drop_off_risk(user_id, values, today) if stage_code == "APP" else None,
        "graduation_risk_flags": _graduation_risk(user_id, values, today) if stage_code in _STUDY_STAGES else [],
    }


def recompute(user_id: str) -> dict:
    labels = compute_labels(user_id)
    profile_interface.save_derived_labels(user_id, labels, rules.RULES_VERSION)
    return labels


def refresh_if_stale(user_id: str) -> None:
    """For a returning user: recompute when never computed, computed by
    older rules, or older than REFRESH_AFTER."""
    stored = profile_interface.get_derived_labels(user_id)
    if (
        stored is None
        or stored.get("rules_version") != rules.RULES_VERSION
        or stored.get("computed_at") is None
        or datetime.now(timezone.utc) - stored["computed_at"] > REFRESH_AFTER
    ):
        recompute(user_id)


def register() -> None:
    events.subscribe(events.PROFILE_CHANGED, recompute)
    events.subscribe(events.USER_SEEN, refresh_if_stale)
