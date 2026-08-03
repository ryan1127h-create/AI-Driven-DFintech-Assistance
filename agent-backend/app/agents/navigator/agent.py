"""#7 Navigator Agent entry point.

Recommends modules for a target role and surfaces skill gaps. The rule engine
decides modules and gaps; the LLM only writes the `explanation` of why.
"""
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse
from common.profile import UserProfile

from .engine import (
    build_candidates, guide_for_role, pick_primary_role, select_modules,
    unrecognized_completed,
)
from .planner import PATHWAYS, graduation_progress, prereq_warnings, what_if_pathways

_SYSTEM = (
    "You advise a Master's student on module choices for a target job role. "
    "Explain in 2-3 plain sentences why the selected modules fit and which gap "
    "to prioritise. Do not invent modules."
)


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    role = pick_primary_role(profile, slots)
    if role is None:
        return AgentResponse.needs(
            ["target_roles"],
            "Please tell me your target role (for example, fintech product manager or quantitative risk analyst) so I can recommend suitable modules.",
        )

    g = guide_for_role(profile, role)
    personalized = profile.consent_flags.personalization
    skill_gaps_labels = g.skill_gap_labels if personalized else []

    candidates = build_candidates(profile, role)
    selected, rationale, source = select_modules(
        candidates, g.skill_gaps, n=4, personalized=personalized
    )
    selected_codes = [m["code"] for m in selected]

    warnings = [
        {"code": w.code, "missing": w.missing}
        for w in prereq_warnings(selected_codes, profile.completed_modules)
        if not w.satisfied
    ]
    progress = graduation_progress(profile.completed_modules, selected_codes)
    # Per-pathway: an infeasible part-time layout must not hide a valid full-time one.
    plans, plan_error = what_if_pathways(selected_codes, profile.completed_modules)
    unknown = unrecognized_completed(profile.completed_modules)

    module_names = ", ".join(m["name"] for m in selected) or "(no recommended modules available)"
    gap_text = ", ".join(skill_gaps_labels) if skill_gaps_labels else "no obvious skill gaps"
    fallback = (
        f"For {g.title}, you should prioritise: {module_names}. "
        f"The areas you should strengthen are: {gap_text}."
    )
    if source == "llm":
        explanation = rationale
    else:
        explanation = llm.explain(
            _SYSTEM,
            f"Target role: {g.title}\nSelected modules: {module_names}\n"
            f"Skill gaps: {', '.join(skill_gaps_labels) or 'none'}",
            fallback,
        )
    speakable = explanation
    if warnings:
        speakable += f" Note: {len(warnings)} module(s) have prerequisites you have not completed."
    if unknown:
        speakable += f" Also, {len(unknown)} completed module code(s) could not be recognised; please check them."
    if plan_error:
        # Name the pathways that failed: a partial failure must not read as a total one.
        failed = ", ".join(p.replace("_", "-") for p in PATHWAYS if p not in plans)
        speakable += (
            f" I could not build a valid semester timetable for the {failed} pathway;"
            " see the details in the plan notes."
        )

    return AgentResponse(
        status="ok",
        answer_type="recommendation",
        speakable=speakable,
        data={
            "target_role": g.role,
            "recommended": selected,
            "already_completed": g.already_completed,
            "candidate_count": len(candidates),
            "skill_gaps": skill_gaps_labels,
            "personalized": personalized,
            "explanation": explanation,
            "selection_source": source,
            "prereq_warnings": warnings,
            "graduation_progress": progress,
            "study_plans": plans,
            "study_plan_error": plan_error,
            "unrecognized_completed": unknown,
        },
        sources=["role_module_map", "module_skills", "module_catalog"],
    )


_CAREER_SYSTEM = (
    "You give a Master's student career-path guidance for a target role. In 2-3 "
    "plain sentences: name the role's key skills, what they already have, the gap "
    "to prioritise, and which modules help close it. Do not invent modules."
)


def career(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    role = pick_primary_role(profile, slots)
    if role is None:
        return AgentResponse.needs(
            ["target_roles"],
            "Please tell me your target role so I can provide career-path and skill advice.",
        )

    g = guide_for_role(profile, role)
    personalized = profile.consent_flags.personalization
    gap_labels = g.skill_gap_labels if personalized else []

    candidates = build_candidates(profile, role)
    gap_closing = [c for c in candidates if c["closes_gaps"]] if personalized else []
    selected, rationale, source = select_modules(
        gap_closing or candidates, g.skill_gaps, n=4, personalized=personalized
    )
    unknown = unrecognized_completed(profile.completed_modules)

    names = ", ".join(m["name"] for m in selected) or "(none)"
    gap_text = ", ".join(gap_labels) if gap_labels else "no obvious skill gaps"
    fallback = (
        f"Key skills for {g.title}: {', '.join(g.required_skills)}. "
        f"You should prioritise strengthening: {gap_text}; recommended modules such as {names} can help close the gaps."
    )
    explanation = rationale if source == "llm" else llm.explain(
        _CAREER_SYSTEM,
        f"Role: {g.title}\nRequired: {', '.join(g.required_skills)}\n"
        f"Has: {', '.join(g.matched_skills) or 'few'}\nGaps: {', '.join(gap_labels) or 'none'}\n"
        f"Gap-closing modules: {names}",
        fallback,
    )

    return AgentResponse(
        status="ok",
        answer_type="recommendation",
        speakable=explanation,
        data={
            "target_role": g.role,
            "required_skills": g.required_skills,
            "matched_skills": g.matched_skills,
            "skills_from_courses": g.skills_from_courses,
            "skill_gaps": gap_labels,
            "gap_closing_modules": selected,
            "personalized": personalized,
            "explanation": explanation,
            "selection_source": source,
            "unrecognized_completed": unknown,
        },
        sources=["role_module_map", "module_skills"],
    )
