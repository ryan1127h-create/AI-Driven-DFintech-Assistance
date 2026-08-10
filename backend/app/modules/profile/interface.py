"""
Public interface of the profile module — the ONLY file other modules
(chatbot, and any future module) are allowed to import from
app.modules.profile. Everything else in this package (repository, agent,
resume_parser, service internals) is private to this module.

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
    "get_lifecycle_stage",
    "patch_profile",
]


def get_profile(user_id: str) -> dict | None:
    """Public read interface for other modules."""
    return repository.get(user_id)


def patch_profile(user_id: str, fields: dict) -> dict | None:
    """Public write interface for user-confirmed profile updates."""
    return repository.patch(user_id, fields)


def get_lifecycle_stage(user_id: str) -> str | None:
    profile = repository.get(user_id)
    return profile.get("lifecycle_stage") if profile else None


def get_profile_summary_text(user_id: str) -> str:
    """Renders the stored profile into a compact text block for the
    chatbot's system prompt. No profile on file -> empty string (caller
    should skip injecting a SystemMessage entirely in that case)."""
    profile = repository.get(user_id)
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

    if not lines:
        return ""

    return "Known applicant profile (from their uploaded resume, use it but don't recite it verbatim):\n" + "\n".join(lines)
