"""Orchestrator adapter for career planning.

career_planning reads no data itself, so this tool assembles its input
report: the profile's "career" purpose facts (consent-filtered), the role
catalogue and the course-to-role links from the knowledge base. The role
is the one named in the message (when it names a known role family), else
the profile's main target role, else its first listed role; with none,
the student gets an exploration of the roles that fit them instead.
"""

from __future__ import annotations

from datetime import date

from app.domains.knowledge_retrieval.interface import list_course_tags, list_courses, list_role_tags, match_role_tag
from app.domains.profile.interface import get_profile_field, get_profile_for_purpose
from app.domains.specialist.career_planning.interface import plan_career
from app.tools.contracts import MissingInputField, OnEvent, Tool, ToolAnswer
from app.tools.input_needs import profile_field_need
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

_ROLE_PROMPT = (
    "Which role are you aiming for? I'll plan your readiness for it — or skip to see which roles fit you."
)

CAREER_STYLE_PROMPT = """\
You are the Career Readiness Advisor for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Walk the user through the career result computed for them: role fit, \
graded skills with the evidence each grade rests on, and (for a plan) the \
dated roadmap.

Hard rules:
- Every grade, fit and date below was computed by a separate, validated \
step — present it as such; never invent skills, employers, salaries or dates.
- A skill marked unknown has no evidence either way: say so, never call it \
a weakness.
- Courses may be mentioned only as evidence the user already has (taken or \
taking) or as the number of programme courses supporting a role; never \
recommend specific courses — point course choice to course recommendations.
- Dates marked projected repeat the last published Capstone cycle; say they \
are to be confirmed.
- If NOTES flag missing evidence or estimates, state that plainly."""

_LEVEL_FIELDS = ("code_level", "ml_ai_level", "data_engineering_level", "blockchain_level",
                 "finance_level", "math_stats_level")
_LIST_FIELDS = ("tech_stack", "domain_knowledge", "certifications", "prior_coursework")
_TEXT_FIELDS = ("degree_discipline_category", "total_work_years", "seniority_level", "employment_status")
_SITUATION_FIELDS = ("career_goal_clarity", "program_motivation", "expected_grad_term",
                     "job_search_timeline", "internship_status", "capstone_intent")


def _career_facts(state: TurnState) -> dict:
    return get_profile_for_purpose(state.user_id, "career") if state.user_id else {}


def _profile_role(facts: dict) -> str | None:
    families = facts.get("target_role_families") or []
    return facts.get("main_target_role") or (families[0] if families else None)


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


def _report(state: TurnState, facts: dict) -> dict:
    role = (match_role_tag(state.target_role_hint) if state.target_role_hint else None) or _profile_role(facts)
    profile = {key: facts[key] for key in (*_LEVEL_FIELDS, *_LIST_FIELDS, *_TEXT_FIELDS) if facts.get(key) is not None}
    profile["function_experience"] = _functions(facts.get("function_experience"))
    profile["completed_courses"] = _codes(facts.get("completed_modules"))
    profile["current_courses"] = _codes(facts.get("current_modules"))
    situation = {key: facts[key] for key in _SITUATION_FIELDS if facts.get(key) is not None}
    situation["target_markets"] = facts.get("target_markets") or []
    situation["stage"] = get_profile_field(state.user_id, "lifecycle_stage") if state.user_id else None

    roles = list_role_tags()
    # Only courses on offer count as the programme's support for a role.
    titles = {row["course_code"]: row["title"] for row in list_courses() if row.get("can_recommend")}
    return {
        "user_id": state.user_id,
        "mode": "plan" if role else "exploration",
        "today": date.today(),
        "target_roles": [role] if role else [],
        "preferred_roles": facts.get("target_role_families") or [],
        "profile": profile,
        "situation": situation,
        "role_catalog": [
            {"tag": r["tag"], "name": r["name_en"], "definition": r.get("definition") or "",
             "required_skills": r["required_skills"]}
            for r in roles if r["required_skills"]
        ],
        "course_links": [
            {"code": code, "title": titles[code], "tags": tags}
            for code, tags in list_course_tags().items() if code in titles
        ],
    }


def _input_needs(state: TurnState) -> tuple[MissingInputField, ...]:
    """The target role is optional: without one the student is shown the
    roles that fit them, and may name one to plan for."""
    if state.target_role_hint:
        return ()
    facts = _career_facts(state)
    if _profile_role(facts):
        return ()
    need = profile_field_need(state, "career", facts, "main_target_role", "optional", _ROLE_PROMPT)
    return (need,) if need else ()


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    result = plan_career(_report(state, _career_facts(state)))
    answer, sources = render_structured_reply(
        result, last_human_message(state.messages), CAREER_STYLE_PROMPT,
        on_event=on_event, depth=state.answer_depth,
    )
    return ToolAnswer(text=answer, sources=sources, agent_used="career_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(
        text=(
            "I couldn't build a reliable career plan right now. Please try again shortly; "
            "your target role and profile will be used when the planning service is available."
        ),
        agent_used="career_agent_fallback",
    )


CAREER_TOOL = Tool(
    name="career",
    description="Career-fit exploration, role readiness with a dated roadmap, and role comparison.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"career"}),
    input_needs=_input_needs,
)
