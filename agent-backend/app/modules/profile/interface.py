"""
Public interface of the profile module — the ONLY file other modules are
allowed to import from app.modules.profile. Everything else in this
package (repository, agent, resume_parser, service internals) is private
to this module.

Current consumers:
    - chatbot::service.py uses get_profile_summary_text() to inject the
      applicant's profile into the conversation.
    - course_recommendation, program_comparison, and career_planning's
      service.py all use get_profile() (and TEST_USER_ID as their default
      user_id) for personalisation.
    - checklist::interface.py/service.py use TEST_USER_ID as their default
      user_id, same reason.

Usage (see app/modules/chatbot/service.py):
    from app.modules.profile.interface import TEST_USER_ID, get_profile_summary_text
"""

from __future__ import annotations

from app.modules.profile import repository
from app.modules.profile.constants import TEST_USER_ID

__all__ = [
    "TEST_USER_ID",
    "get_profile",
    "get_profile_summary_text",
    "render_profile_summary",
]


def get_profile(user_id: str) -> dict | None:
    """Public read interface for other modules."""
    return repository.get(user_id)


def get_profile_summary_text(user_id: str) -> str:
    """Fetches the profile and renders it — see render_profile_summary()
    if you already have the profile dict (e.g. via get_profile()) and want
    to avoid fetching it twice."""
    return render_profile_summary(repository.get(user_id))


def render_profile_summary(profile: dict | None) -> str:
    """Pure rendering of an already-fetched profile dict into the same
    compact text block get_profile_summary_text() produces — no I/O. No
    profile on file -> empty string (caller should skip injecting a
    SystemMessage entirely in that case)."""
    if not profile:
        return ""

    lines = []

    def _raw_std(raw_field: str, std_field: str, label: str):
        raw, std = profile.get(raw_field), profile.get(std_field)
        if std or raw:
            lines.append(f"- {label}: {std or raw}")

    _raw_std("academic_background_raw", "academic_background_std", "Academic background")
    if profile.get("school_tier"):
        lines.append(f"- Undergrad tier: {profile['school_tier']}")
    _raw_std("tech_level_raw", "tech_level_std", "Technical level")
    if profile.get("work_years") is not None:
        lines.append(f"- Work experience: {profile['work_years']} years")
    for field, label in [("gmat", "GMAT"), ("gre", "GRE"), ("toefl", "TOEFL"), ("ielts", "IELTS")]:
        if profile.get(field) is not None:
            lines.append(f"- {label}: {profile[field]}")
    _raw_std("target_role_raw", "target_role_std", "Target career")
    _raw_std("target_industry_raw", "target_industry_std", "Target industry")
    if profile.get("lifecycle_stage"):
        lines.append(f"- Lifecycle stage: {profile['lifecycle_stage']}")
    if profile.get("application_term"):
        lines.append(f"- Application term: {profile['application_term']}")
    if profile.get("intake_year"):
        lines.append(f"- Intake year: {profile['intake_year']}")
    if profile.get("completed_courses"):
        courses = ", ".join(profile["completed_courses"])
        lines.append(f"- Relevant prior/completed courses: {courses}")

    if not lines:
        return ""

    return "Known applicant profile (from their uploaded resume, use it but don't recite it verbatim):\n" + "\n".join(lines)
