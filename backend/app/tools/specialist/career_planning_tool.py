"""Orchestrator adapter for independent career-readiness planning."""

from __future__ import annotations

from app.domains.profile.interface import get_profile
from app.domains.specialist.career_planning.interface import create_career_plan
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


def _has_known_target_role(state: TurnState) -> bool:
    if state.target_role_hint:
        return True
    profile = get_profile(state.user_id) if state.user_id else None
    return bool((profile or {}).get("target_role_raw") or (profile or {}).get("target_role_std"))


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

    result = create_career_plan(user_id=state.user_id, target_role=state.target_role_hint)
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(result, user_message, CAREER_STYLE_PROMPT, on_event=on_event)
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
