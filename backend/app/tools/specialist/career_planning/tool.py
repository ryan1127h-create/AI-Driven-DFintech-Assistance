"""
The career planning Tool: registration plus a handler that only sequences
the workflow's steps — S1 reads the message (s1_understanding/) while S2
gathers the turn's data, S2 then builds the report (s2_assembly/), the
domain runs S3-S6 on that one report, and S7 renders the reply
(s7_presentation/). No business rule lives in this module.

Profile facts come from the profile's "career" purpose (consent-filtered;
empty without consent, in which case the advice is not personalised).
"""

from __future__ import annotations

import concurrent.futures
from datetime import date

from app.core.logging import get_logger
from app.domains.specialist.career_planning.interface import plan_career
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.specialist.career_planning.gate import input_needs
from app.tools.specialist.career_planning.s1_understanding import parser
from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly.builder import build_report
from app.tools.specialist.career_planning.s2_assembly.prefetch import prefetch, role_catalog
from app.tools.specialist.career_planning.s7_presentation import renderer
from app.tools.specialist.career_planning.s7_presentation.save_suggestions import save_suggestions
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

logger = get_logger(__name__)

# Parsing runs while S2 gathers data; past this it's dropped, not waited on.
_PARSE_TIMEOUT_SECONDS = 15.0

_FALLBACK_REPLY = (
    "I couldn't put together reliable career advice right now. Please try again shortly; your target role "
    "and profile will be used when the planning service is available."
)


def _understand_and_gather(state: TurnState, user_message: str):
    """S1 and S2's reads, in parallel: neither needs the other (the parser
    only needs the role catalogue, which is cached)."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        parsing = pool.submit(parser.parse, user_message, role_catalog())
        prefetched = prefetch(state.user_id)
        try:
            parsed = parsing.result(timeout=_PARSE_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("career planning: parsing didn't finish, using the profile alone")
            parsed = ParsedCareerRequest(parse_failed=True)
    finally:
        pool.shutdown(wait=False)
    return parsed, prefetched


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    user_message = last_human_message(state.messages)
    parsed, prefetched = _understand_and_gather(state, user_message)
    built = build_report(prefetched, parsed, state.career_mode_hint, date.today(), state.user_id)

    result = plan_career(built.report)
    result["notes"] = [*built.notes, *prefetched.notes, *result["notes"]]
    answer, sources = renderer.render(result, prefetched, user_message, on_event=on_event, depth=state.answer_depth)
    return ToolAnswer(
        text=answer, sources=sources, agent_used="career_agent",
        save_suggestions=save_suggestions(parsed, prefetched, result["mode"]),
    )


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="career_agent_fallback")


CAREER_TOOL = Tool(
    name="career",
    description="Career-fit exploration, role readiness with a dated roadmap, and role comparison.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"career"}),
    input_needs=input_needs,
    # Grades, fits and dates are computed deterministically and renderer.py
    # checks the reply against them, so evaluation would only add a model call.
    skip_evaluation=True,
)
