"""
The application readiness assessment Tool: registration plus a handler
that only sequences the steps — S1 reads what the message states about the
applicant (s1_understanding/) while S2 gathers the profile and MSc DFT's
checked requirements, S2 builds the report (s2_assembly/), the domain
decides the hard conditions and soft factors on that one report, and S7
writes the reply, the save suggestions and the quick-fill card
(s7_presentation/). No business rule lives in this module.

Profile facts come from the profile's "adm" and "career" purposes (one
consent; without it the assessment runs on the message alone and says so).
"""

from __future__ import annotations

import concurrent.futures

from app.core.logging import get_logger
from app.domains.specialist.assessment import interface as assessment
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.specialist.assessment.s1_understanding import parser
from app.tools.specialist.assessment.s1_understanding.schema import StatedFacts
from app.tools.specialist.assessment.s2_assembly.builder import build_report
from app.tools.specialist.assessment.s2_assembly.prefetch import prefetch
from app.tools.specialist.assessment.s7_presentation import missing_info, renderer
from app.tools.specialist.assessment.s7_presentation.payload import to_render_view
from app.tools.specialist.assessment.s7_presentation.save_suggestions import save_suggestions
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

logger = get_logger(__name__)

# Parsing runs while S2 gathers data; past this it's dropped, not waited on.
_PARSE_TIMEOUT_SECONDS = 15.0

_UNAVAILABLE_REPLY = (
    "I can't check your readiness right now — the programme's admission requirements couldn't be loaded. "
    "Please try again shortly."
)
_FALLBACK_REPLY = (
    "I couldn't complete the readiness check right now. Please try again shortly, or ask about the admission "
    "requirements directly."
)


def _understand_and_gather(state: TurnState, user_message: str):
    """S1 and S2's reads, in parallel: neither needs the other."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        parsing = pool.submit(parser.parse, user_message)
        prefetched = prefetch(state.user_id)
        try:
            stated = parsing.result(timeout=_PARSE_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("assessment: parsing didn't finish, using the profile alone")
            stated = StatedFacts(parse_failed=True)
    finally:
        pool.shutdown(wait=False)
    return stated, prefetched


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    user_message = last_human_message(state.messages)
    stated, prefetched = _understand_and_gather(state, user_message)
    report = build_report(prefetched, stated)
    if report is None:
        return ToolAnswer(text=_UNAVAILABLE_REPLY, agent_used="assessment_agent_unavailable")

    result = assessment.assess(report)
    view = to_render_view(result, prefetched, notes=prefetched.notes)
    answer, sources = renderer.render(
        view, user_message, on_event=on_event, depth=state.answer_depth, language=state.reply_language,
        other_tools=state.other_tools,
    )
    return ToolAnswer(
        text=answer, sources=sources, agent_used="assessment_agent",
        save_suggestions=save_suggestions(stated, prefetched),
        supplement_card=missing_info.card(result["missing_fields"], prefetched),
        contexts=[{"tool": "assessment", "mode": "readiness", "subjects": [result["verdict"]], "awaiting": None}],
    )


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="assessment_agent_fallback")


ASSESSMENT_TOOL = Tool(
    name="assessment",
    description="Application readiness: the hard conditions an application must meet and how competitive it is.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"assessment"}),
    # The conditions and factors are decided by code and renderer.py checks
    # the reply against them, so evaluation would only add a model call.
    skip_evaluation=True,
)
