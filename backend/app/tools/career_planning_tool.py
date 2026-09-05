"""
Career tool — personalised career-fit assessment, skill-gap analysis, and
course recommendations for a target role.

Backed by career_planning.interface.create_career_plan(), which itself
reuses course_recommendation (role -> skills -> eligible courses -> LLM
pick) plus a knowledge_retrieval pass over the "career" topic for
narrative context. This tool's own job is only: resolve the inputs
create_career_plan() needs from the turn context (user_id, an optional
target_role hint the orchestrator's intent classifier extracted), call it,
and reflow its structured result into one chat reply via
structured_reply.render_structured_reply().

If create_career_plan() (or the reflow step) raises for any reason, this
falls back to plain RAG over the knowledge base's "career" topic — so a
bug or outage in the career_planning integration degrades to a strictly
worse but still working answer, never a failed turn. That fallback is
registered on the Tool itself (see CAREER_TOOL below), not hand-rolled
here — the registry already knows how to run a fallback on any handler
failure.
"""

from __future__ import annotations

from app.domains.career_planning.interface import create_career_plan
from app.domains.knowledge_retrieval.interface import cited_sources
from app.domains.profile.interface import get_profile
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.rag_retrieve import CAREER_STYLE_PROMPT, LEGACY_CAREER_SPEC, run_rag
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

_NEEDS_ROLE_REPLY = (
    "To plan courses and next steps around a specific career, I need to know "
    "which role you're aiming for — e.g. quant researcher, compliance officer, "
    "fintech product manager, risk analyst. What role are you targeting?"
)


def _has_known_target_role(state: TurnState) -> bool:
    """A career plan needs a target role from somewhere — either named in
    this turn (target_role_hint, from the intent classifier) or already on
    file in the applicant's profile. Checked deterministically, in code,
    rather than letting create_career_plan() silently guess: a plan built
    with no role signal at all degrades to generic, low-value output."""
    if state.target_role_hint:
        return True
    profile = get_profile(state.user_id) if state.user_id else None
    return bool((profile or {}).get("target_role_raw") or (profile or {}).get("target_role_std"))


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    if not _has_known_target_role(state):
        return ToolAnswer(text=_NEEDS_ROLE_REPLY, agent_used="career_agent", needs_clarification=True)

    result = create_career_plan(user_id=state.user_id, target_role=state.target_role_hint)
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(result, user_message, CAREER_STYLE_PROMPT, on_event=on_event)
    return ToolAnswer(text=answer, sources=sources, agent_used="career_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    print("[career_tool] Warning: career_planning integration failed, falling back to RAG")
    answer, hits = run_rag(LEGACY_CAREER_SPEC, state.messages, on_event=on_event)
    return ToolAnswer(text=answer, sources=cited_sources(hits), agent_used="career_agent_fallback")


CAREER_TOOL = Tool(
    name="career",
    description="Personalised career-fit assessment, skill-gap analysis, and course recommendations for a target role.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"career"}),
)
