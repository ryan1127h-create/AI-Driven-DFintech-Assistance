"""Career-planning orchestration behind the career-plans endpoint.

The domain deliberately owns a career-readiness flow rather than delegating
to course recommendation:

    target role -> career evidence -> role context -> phased action plan

Profile data is read through the profile domain. Career reference material
comes from the shared knowledge-retrieval domain. Academic material is
excluded before anything reaches the planning LLM.
"""

from __future__ import annotations

import re

from app.core.errors import ValidationError
from app.domains.career_planning import planning_agent
from app.domains.career_planning.models import CareerPlanResult
from app.domains.knowledge_retrieval.interface import cited_sources, retrieve
from app.domains.profile.interface import get_profile


_ACADEMIC_LINE = re.compile(
    r"\b(?:course|courses|module|modules|curriculum|elective|nusmods)\b"
    r"|\b[A-Z]{2,4}\d{4}[A-Z]?\b"
    r"|(?:课程|选修课|必修课|课程代码|模块)",
    re.IGNORECASE,
)


def _resolve_target_role(requested_role: str | None, profile: dict | None) -> str:
    """Request value wins; otherwise use the best role evidence on file."""
    for value in (
        requested_role,
        (profile or {}).get("target_role_std"),
        (profile or {}).get("target_role_raw"),
    ):
        if isinstance(value, str) and value.strip():
            role = value.strip()
            if _ACADEMIC_LINE.search(role):
                raise ValidationError(
                    "TARGET_ROLE_INVALID: provide a job role rather than an academic selection request."
                )
            return role
    raise ValidationError(
        "TARGET_ROLE_REQUIRED: provide a target role or add one to your profile before creating a career plan."
    )


def _career_profile_summary(profile: dict | None) -> str:
    """Render only career-relevant evidence; intentionally excludes study history."""
    if not profile:
        return ""

    lines: list[str] = []

    def _raw_or_standard(raw_field: str, standard_field: str, label: str) -> None:
        value = profile.get(standard_field) or profile.get(raw_field)
        if value:
            lines.append(f"- {label}: {value}")

    _raw_or_standard("academic_background_raw", "academic_background_std", "Academic background")
    _raw_or_standard("tech_level_raw", "tech_level_std", "Technical level")
    if profile.get("work_years") is not None:
        lines.append(f"- Work experience: {profile['work_years']} years")
    _raw_or_standard("target_industry_raw", "target_industry_std", "Target industry")
    if profile.get("lifecycle_stage"):
        lines.append(f"- Career stage: {profile['lifecycle_stage']}")

    if not lines:
        return ""
    return "Known career evidence from the user's profile:\n" + "\n".join(lines)


def _clean_reference_text(value: object) -> str:
    """Drop lines that can steer the plan back toward academic recommendations."""
    if not isinstance(value, str):
        return ""
    return "\n".join(
        line.strip()
        for line in value.splitlines()
        if line.strip() and not _ACADEMIC_LINE.search(line)
    )


def _clean_optional_hint(value: str | None) -> str | None:
    """Keep timeline/region hints only when they cannot reintroduce academic text."""
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.strip()
    return None if _ACADEMIC_LINE.search(cleaned) else cleaned


def _career_context(hits: list, requested_role: str) -> tuple[str, str]:
    """Build course-free context, using structured role metadata where available."""
    blocks: list[str] = []
    resolved_title = requested_role

    for hit in hits:
        metadata = hit.metadata if isinstance(hit.metadata, dict) else {}
        if hit.source_table == "career_roles":
            role_id = str(metadata.get("role_id") or "").strip()
            role_title = str(metadata.get("role_title") or "").strip()
            raw_skills = metadata.get("required_skills") or []
            if not isinstance(raw_skills, (list, tuple)):
                raw_skills = []
            skills = [
                str(skill).replace("_", " ").strip()
                for skill in raw_skills
                if str(skill).strip()
            ]

            if requested_role.casefold() in {role_id.casefold(), role_title.casefold()} and role_title:
                resolved_title = role_title

            facts = []
            if role_title:
                facts.append(f"Role: {role_title}")
            if skills:
                facts.append("Typical capability areas: " + ", ".join(skills))
            if facts:
                blocks.append("\n".join(facts))
            continue

        context = _clean_reference_text(hit.context)
        content = _clean_reference_text(hit.content)
        block = "\n".join(part for part in (context, content) if part)
        if block:
            blocks.append(block)

    return "\n\n".join(blocks), resolved_title


def create_career_plan(
    user_id: str | None = None,
    target_role: str | None = None,
    timeline: str | None = None,
    region: str | None = None,
) -> CareerPlanResult:
    profile = get_profile(user_id) if user_id else None
    requested_role = _resolve_target_role(target_role, profile)
    profile_summary = _career_profile_summary(profile)
    timeline = _clean_optional_hint(timeline)
    region = _clean_optional_hint(region)

    hits = retrieve(
        f"career pathway responsibilities skills experience portfolio hiring {requested_role}",
        top_k=3,
        filter_topics={"career"},
    )
    career_context, role_title = _career_context(hits, requested_role)

    plan = None
    if career_context:
        plan = planning_agent.write_plan(
            profile_summary=profile_summary,
            role_title=role_title,
            career_context=career_context,
            timeline=timeline,
            region=region,
        )
    if plan is None:
        plan = planning_agent.fallback_plan(
            role_title=role_title,
            has_profile=bool(profile_summary),
            timeline=timeline,
            region=region,
        )

    notes = list(plan["notes"])
    if not profile_summary:
        notes.insert(
            0,
            "No career evidence was available from the profile; unsupported capabilities are left unassessed.",
        )
    if not career_context:
        notes.append(
            "Career reference material was unavailable, so the plan uses a conservative readiness checklist."
        )

    return CareerPlanResult(
        target_role=role_title,
        current_fit=plan["current_fit"],
        skill_assessment=tuple(plan["skill_assessment"]),
        phases=tuple(plan["phases"]),
        success_indicators=tuple(plan["success_indicators"]),
        notes=tuple(notes),
        sources=tuple(cited_sources(hits)),
    )
