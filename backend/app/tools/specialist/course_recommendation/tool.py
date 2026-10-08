"""
The course_recommendation Tool: registration plus a handler that only
sequences the workflow's steps — S2 gathers the turn's data and assembles
the report (s2_assembly/), the domain runs S3-S6 (it consumes that one
report and does no profile or knowledge-base lookups of its own), and S7
renders the reply (s7_presentation/). No business rule lives in this
module.

Profile facts come from the profile's "course" purpose (consent-filtered;
empty without consent, in which case the recommendation is simply not
personalised).
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.interface import recommend_courses
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.specialist.course_recommendation.s2_assembly.builder import build_request, other_roles_note
from app.tools.specialist.course_recommendation.s2_assembly.prefetch import prefetch
from app.tools.specialist.course_recommendation.s7_presentation import renderer
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

_FALLBACK_REPLY = (
    "I couldn't put together a reliable course recommendation right now. "
    "Please try again shortly."
)


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    prefetched = prefetch(state.user_id, state.target_role_hint)

    result = recommend_courses(build_request(prefetched))
    # Graduation risks aren't a recommendation input; they ride along so the
    # reply can point them out, as do any limits met while gathering data.
    result["notes"].extend(prefetched.graduation_notes)
    result["notes"].extend(prefetched.notes)
    note = other_roles_note(prefetched)
    if note:
        result["notes"].append(note)
    user_message = last_human_message(state.messages)
    answer, sources = renderer.render(result, user_message, on_event=on_event, depth=state.answer_depth)
    return ToolAnswer(text=answer, sources=sources, agent_used="course_recommendation_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="course_recommendation_agent_fallback")


COURSE_RECOMMENDATION_TOOL = Tool(
    name="course_recommendation",
    description="Personalised course recommendations from the applicant's profile and the current curriculum.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"course_recommendation"}),
)
