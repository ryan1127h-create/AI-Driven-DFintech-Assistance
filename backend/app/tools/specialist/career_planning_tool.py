"""Orchestrator adapter for independent career-readiness planning.

career_planning reads no data itself, so this tool assembles its inputs:
the target role (named in the message, else the profile's main target role,
else its first target role family), the user's career evidence (the
profile's "career" purpose facts plus lifecycle stage, as English lines) and
the career reference chunks retrieved for that role.
"""

from __future__ import annotations

from dataclasses import asdict

from app.domains.knowledge_retrieval.interface import get_role_profile
from app.domains.profile.interface import describe_facts, describe_value, get_profile_field, get_profile_for_purpose
from app.domains.specialist.career_planning.interface import create_career_plan
from app.tools.knowledge_context import retrieve_context
from app.tools.contracts import MissingInputField, OnEvent, Tool, ToolAnswer
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

_NEEDS_ROLE_REPLY = (
    "To build a useful career-readiness plan, I need to know which role you're "
    "aiming for — e.g. quant researcher, compliance officer, fintech product "
    "manager, or risk analyst. What role are you targeting?"
)

CAREER_STYLE_PROMPT = """\
You are the Career Readiness Advisor for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your role is to walk the user through an evidence-based career-readiness plan \
for their stated target role, using the fit assessment, skill evidence, and \
phased action plan already computed for them.

Hard rules:
- Every skill assessment and phase below is grounded in evidence from the \
user's own profile/career background, computed by a separate, already-validated \
step — present it as such, never as a generic or invented judgement.
- Do NOT recommend or mention specific courses, modules, or course codes, even \
if the user's message brings them up — this plan is deliberately independent of \
course selection; point course-selection questions to the programme's academic \
advising instead.
- Phase timeframes and success indicators are a realistic roadmap the user can \
self-check against, not a guarantee or an official requirement.
- If NOTES below flag missing evidence (e.g. no profile on file), be upfront \
about that limitation rather than glossing over it."""


def _career_facts(state: TurnState) -> dict:
    return get_profile_for_purpose(state.user_id, "career") if state.user_id else {}


def _target_role(state: TurnState, facts: dict) -> str | None:
    """The role named in the message, else the profile's main role, else
    its first listed role (as the role family's English name)."""
    if state.target_role_hint:
        return state.target_role_hint
    families = facts.get("target_role_families") or []
    tag = facts.get("main_target_role") or (families[0] if families else None)
    if not tag:
        return None
    role = get_role_profile(tag)
    return role["role_title"] if role else tag


def _evidence(state: TurnState, facts: dict) -> list[str]:
    lines = describe_facts(facts)
    stage = get_profile_field(state.user_id, "lifecycle_stage") if state.user_id else None
    if stage:
        lines.append("Career stage: " + describe_value("lifecycle_stage", stage))
    return lines


def _has_known_target_role(state: TurnState) -> bool:
    return bool(_target_role(state, _career_facts(state)))


def _required_input(state: TurnState) -> tuple[MissingInputField, ...]:
    if _has_known_target_role(state):
        return ()
    return (MissingInputField(slot="target_role", prompt=_NEEDS_ROLE_REPLY),)


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    # Defense-in-depth only: orchestrator/dispatch/requirements.py already
    # checks _required_input() for every matched tool before any of them
    # is invoked, so this branch is unreachable via the normal dispatch
    # path — kept so a direct/bypassing caller (e.g. registry.invoke_typed()
    # from a test, or a future caller outside dispatch) still degrades to a
    # targeted question instead of calling create_career_plan() with
    # nothing to go on.
    if not _has_known_target_role(state):
        return ToolAnswer(
            text=_NEEDS_ROLE_REPLY,
            agent_used="career_agent",
            needs_clarification=True,
        )

    facts = _career_facts(state)
    role = _target_role(state, facts)
    retrieved = retrieve_context(
        f"career pathway responsibilities skills experience portfolio hiring {role}",
        top_k=3, filter_topics={"career"},
    )
    result = create_career_plan(
        role, _evidence(state, facts), [asdict(h) for h in retrieved.hits], retrieved.sources,
    )
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(
        result, user_message, CAREER_STYLE_PROMPT, on_event=on_event, depth=state.answer_depth,
    )
    return ToolAnswer(text=answer, sources=sources, agent_used="career_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    """Fail honestly without switching to an academically-oriented answer path."""
    return ToolAnswer(
        text=(
            "I couldn't build a reliable personalised readiness plan right now. "
            "Please try again shortly; your target role and profile "
            "evidence will be used when the planning service is available."
        ),
        agent_used="career_agent_fallback",
    )


CAREER_TOOL = Tool(
    name="career",
    description="Evidence-based career-fit assessment and phased job-readiness planning.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"career"}),
    required_input=_required_input,
)
