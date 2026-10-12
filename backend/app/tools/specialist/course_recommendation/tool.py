"""
The course_recommendation Tool: registration plus a handler that only
sequences the workflow's steps — S1 reads the message into a structured
request (s1_understanding/) while S2 gathers the turn's data, S2 then
assembles the report (s2_assembly/), the domain runs S3-S6 (it consumes
that one report and does no profile or knowledge-base lookups of its
own), and S7 renders the reply (s7_presentation/). No business rule lives
in this module.

Profile facts come from the profile's "course" purpose (consent-filtered;
empty without consent, in which case the recommendation is simply not
personalised).
"""

from __future__ import annotations

import concurrent.futures

from app.core.logging import get_logger
from app.domains.specialist.course_recommendation.interface import recommend_courses
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.specialist.course_recommendation.gate import input_needs
from app.tools.specialist.course_recommendation.s1_understanding import parser
from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.specialist.course_recommendation.s2_assembly.builder import build_request, other_roles_note
from app.tools.specialist.course_recommendation.s2_assembly.prefetch import prefetch
from app.tools.specialist.course_recommendation.s7_presentation import renderer
from app.tools.specialist.course_recommendation.s7_presentation.save_suggestions import save_suggestions
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

logger = get_logger(__name__)

# Parsing runs while S2 gathers data; past this it's dropped, not waited on.
_PARSE_TIMEOUT_SECONDS = 15.0

_PARSE_FAILED_NOTE = (
    "The specific preferences in the message couldn't be made out, so this "
    "recommendation doesn't apply them."
)

_FALLBACK_REPLY = (
    "I couldn't put together a reliable course recommendation right now. "
    "Please try again shortly."
)


def _understand_and_gather(state: TurnState, user_message: str):
    """S1 and S2's reads, in parallel: neither needs the other."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        parsing = pool.submit(parser.parse, user_message, state.course_mode_hint)
        prefetched = prefetch(state.user_id, state.target_role_hint)
        try:
            parsed = parsing.result(timeout=_PARSE_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("course recommendation: parsing didn't finish, using no filters")
            parsed = ParsedRequest(mode=state.course_mode_hint or "degree_overview", parse_failed=True)
    finally:
        pool.shutdown(wait=False)
    return parsed, prefetched


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    user_message = last_human_message(state.messages)
    parsed, prefetched = _understand_and_gather(state, user_message)

    result = recommend_courses(build_request(prefetched, parsed))
    # Graduation risks aren't a recommendation input; they ride along so the
    # reply can point them out, as do any limits met while gathering data.
    result["notes"].extend(prefetched.graduation_notes)
    result["notes"].extend(prefetched.notes)
    if parsed.parse_failed:
        result["notes"].append(_PARSE_FAILED_NOTE)
    note = other_roles_note(prefetched)
    if note:
        result["notes"].append(note)
    answer, sources = renderer.render(result, user_message, on_event=on_event, depth=state.answer_depth)
    return ToolAnswer(
        text=answer, sources=sources, agent_used="course_recommendation_agent",
        save_suggestions=save_suggestions(parsed, prefetched),
    )


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="course_recommendation_agent_fallback")


COURSE_RECOMMENDATION_TOOL = Tool(
    name="course_recommendation",
    description="Personalised course recommendations from the applicant's profile and the current curriculum.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"course_recommendation"}),
    input_needs=input_needs,
    # The selection is deterministic and renderer.py checks the reply
    # against the result, so evaluation would only add a model call.
    skip_evaluation=True,
)
