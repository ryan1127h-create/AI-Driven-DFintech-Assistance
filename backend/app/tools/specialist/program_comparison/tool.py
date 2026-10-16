"""
The programme comparison Tool: registration plus a handler that only
sequences the workflow's steps — S1 reads the message (s1_understanding/)
while S2 gathers the turn's data, S2 then builds the report
(s2_assembly/), the domain runs S3-S6 on that one report, and S7 renders
the reply (s7_presentation/). No business rule lives in this module.

Applicant facts come from the profile's "adm" purpose (consent-filtered;
empty without consent, in which case the comparison lays out published
facts only and says so).
"""

from __future__ import annotations

import concurrent.futures
from datetime import date

from app.core.logging import get_logger
from app.domains.specialist.program_comparison.interface import compare
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.specialist.program_comparison.gate import input_needs
from app.tools.specialist.program_comparison.s1_understanding import parser
from app.tools.specialist.program_comparison.s1_understanding.schema import ParsedComparisonRequest
from app.tools.specialist.program_comparison.s2_assembly.builder import build_report
from app.tools.specialist.program_comparison.s2_assembly.prefetch import catalogue, prefetch, role_catalog
from app.tools.specialist.program_comparison.s7_presentation import follow_up, renderer
from app.tools.specialist.program_comparison.s7_presentation.save_suggestions import save_suggestions
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

logger = get_logger(__name__)

# Parsing runs while S2 gathers data; past this it's dropped, not waited on.
_PARSE_TIMEOUT_SECONDS = 15.0

_FALLBACK_REPLY = (
    "I couldn't put the programme comparison together right now. Please try again shortly; the comparison "
    "uses each university's published facts, checked against their official pages."
)


def _understand_and_gather(state: TurnState, user_message: str):
    """S1 and S2's reads, in parallel: neither needs the other (the parser
    only needs the catalogue and role families, which are cached, and the
    programmes the previous reply offered, if it asked for a choice)."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        options = follow_up.options_offered(state.previous_turn)
        parsing = pool.submit(parser.parse, user_message, catalogue(), role_catalog(), options)
        prefetched = prefetch(state.user_id)
        try:
            parsed = parsing.result(timeout=_PARSE_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("programme comparison: parsing didn't finish, using hints and the profile")
            parsed = ParsedComparisonRequest(parse_failed=True)
    finally:
        pool.shutdown(wait=False)
    return parsed, prefetched


def _other_universities(programs: list[dict]) -> list[dict]:
    """Every catalogue university but MSc DFT's own: the reply may always
    name NUS (a detail answer offers to compare with MSc DFT)."""
    home = next(p["university"]["university_id"] for p in programs if p["is_target"])
    seen = {}
    for p in programs:
        if p["university"]["university_id"] != home:
            seen.setdefault(p["university"]["university_id"], p["university"])
    return list(seen.values())


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    user_message = last_human_message(state.messages)
    parsed, prefetched = _understand_and_gather(state, user_message)
    built = build_report(
        prefetched, parsed, state.comparison_mode_hint, state.program_hints, date.today(), state.user_id,
        previous_programs=follow_up.programs_covered(state.previous_turn),
    )

    result = compare(built.report)
    result["notes"] = list(dict.fromkeys([*prefetched.notes, *built.notes, *result["notes"]]))
    answer, sources = renderer.render(
        result, _other_universities(prefetched.programs), user_message, on_event=on_event, depth=state.answer_depth, language=state.reply_language,
        other_tools=state.other_tools,
    )
    return ToolAnswer(
        text=answer, sources=sources, agent_used="comparison_agent",
        save_suggestions=save_suggestions(parsed, prefetched, result["mode"]),
        contexts=[follow_up.turn_context(result)],
    )


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="comparison_agent_fallback")


COMPARISON_TOOL = Tool(
    name="comparison",
    description="MSc DFT compared with other master's programmes on verified, sourced facts, related to the applicant.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"comparison"}),
    input_needs=input_needs,
    # Figures, dates and differences come from verified catalogue facts and
    # renderer.py checks the reply against them, so evaluation would only
    # add a model call.
    skip_evaluation=True,
)
