"""
S2 — builds the domain's CareerPlanningInput from what prefetch gathered
and what S1 parsed. Pure: no reads.

Which mode actually runs, and for which roles:

    compare      the roles the message names, topped up from the profile
                 (main role first) to two or three; with only one, a
                 plan for it; with none, an exploration
    plan         the first role the message names, else the profile's
                 main role (then its first listed one); with none, an
                 exploration — the student sees which roles fit, and is
                 offered the role field alongside
    exploration  every role — unless the message names roles: one is
                 planned for, two or three compared (a student picking a
                 role from an exploration is asking for its plan)

No mode from the classifier: two named roles compare, one (or a profile
role) plans, none explores. Each fallback adds a note saying what ran
instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched

# The programme pages the career facts come from: the Capstone cycle and
# the career channels (FAQ).
SOURCES = (
    "https://www.comp.nus.edu.sg/programmes/pg/mdft/capstone/",
    "https://www.comp.nus.edu.sg/programmes/pg/mdft/faq/",
)

_LEVEL_FIELDS = ("code_level", "ml_ai_level", "data_engineering_level", "blockchain_level",
                 "finance_level", "math_stats_level")
_LIST_FIELDS = ("tech_stack", "domain_knowledge", "certifications", "prior_coursework")
_TEXT_FIELDS = ("degree_discipline_category", "total_work_years", "seniority_level", "employment_status")
_SITUATION_FIELDS = ("career_goal_clarity", "program_motivation", "expected_grad_term", "capstone_intent")
_MAX_COMPARE = 3

_NOTES = {
    "no_role_for_plan": (
        "No target role is set yet, so here are the roles your profile fits best; name one (or save it to "
        "your profile) for a full readiness plan."
    ),
    "one_role_for_compare": "Only one role was given to compare, so this is a readiness plan for {role} instead.",
    "no_role_for_compare": "No roles were given to compare, so here are the roles your profile fits best.",
    "unmatched": (
        "{names} doesn't match any of the programme's role families, so the advice uses the closest "
        "information available."
    ),
    "parse_failed": "The details in your message couldn't be made out, so this is based on your profile alone.",
}


@dataclass(frozen=True)
class Built:
    report: dict
    notes: tuple[str, ...]


def _codes(items) -> list[str]:
    return [item.get("course_code") if isinstance(item, dict) else item for item in items or []]


def _functions(items) -> list[dict]:
    result = []
    for item in items or []:
        if isinstance(item, dict) and item.get("key"):
            result.append({"key": item["key"], "internship": bool(item.get("internship"))})
        elif isinstance(item, str):
            result.append({"key": item})
    return result


def resolve_mode(
    mode_hint: str | None, parsed: ParsedCareerRequest, prefetched: Prefetched,
) -> tuple[str, list[str], list[str]]:
    """(mode, target roles, notes)."""
    named = parsed.roles
    profile = [r for r in prefetched.profile_roles if r not in named]
    names = {r["tag"]: r["name"] for r in prefetched.role_catalog}
    mode = mode_hint or ("compare" if len(named) >= 2 else "plan" if named or profile else "exploration")
    if mode == "exploration" and named:
        mode = "compare" if len(named) >= 2 else "plan"

    if mode == "compare":
        roles = (named + profile)[:_MAX_COMPARE]
        if len(roles) >= 2:
            return "compare", roles, []
        if roles:
            return "plan", roles, [_NOTES["one_role_for_compare"].format(role=names[roles[0]])]
        return "exploration", [], [_NOTES["no_role_for_compare"]]
    if mode == "plan":
        roles = (named + profile)[:1]
        if roles:
            return "plan", roles, []
        return "exploration", [], [_NOTES["no_role_for_plan"]]
    return "exploration", [], []


def build_report(
    prefetched: Prefetched,
    parsed: ParsedCareerRequest,
    mode_hint: str | None,
    today: date,
    user_id: str | None = None,
) -> Built:
    facts = prefetched.facts
    mode, roles, notes = resolve_mode(mode_hint, parsed, prefetched)
    if parsed.unmatched_roles:
        notes.append(_NOTES["unmatched"].format(names=", ".join(f'"{r}"' for r in parsed.unmatched_roles)))
    if parsed.parse_failed:
        notes.append(_NOTES["parse_failed"])

    profile = {key: facts[key] for key in (*_LEVEL_FIELDS, *_LIST_FIELDS, *_TEXT_FIELDS)
               if facts.get(key) not in (None, "", [])}
    profile["function_experience"] = _functions(facts.get("function_experience"))
    profile["completed_courses"] = _codes(facts.get("completed_modules"))
    profile["current_courses"] = _codes(facts.get("current_modules"))

    # What the message states this turn outranks the profile.
    situation = {key: facts[key] for key in _SITUATION_FIELDS if facts.get(key) is not None}
    situation["stage"] = prefetched.stage
    situation["job_search_timeline"] = parsed.job_search_timeline or facts.get("job_search_timeline")
    situation["internship_status"] = parsed.internship_status or facts.get("internship_status")
    situation["target_markets"] = parsed.target_markets or facts.get("target_markets") or []

    report = {
        "user_id": user_id,
        "mode": mode,
        "today": today,
        "target_roles": roles,
        "preferred_roles": prefetched.profile_roles,
        "profile": profile,
        "situation": situation,
        "readiness_gaps": prefetched.readiness_gaps,
        "role_catalog": prefetched.role_catalog,
        "course_links": prefetched.course_links,
        "evidence_sources": list(SOURCES),
    }
    return Built(report=report, notes=tuple(notes))
