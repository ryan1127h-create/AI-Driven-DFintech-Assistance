"""
S7 — renders the assessment into the chat reply.

Streams a reply from the render view (payload.py) under the style prompt,
then checks it against that view (guardrail.py). A reply that fails the
check is rendered once more, silently, with the violations spelled out;
if that still fails, the deterministic template reply is used instead.
The streamed first draft is never left standing: the client replaces it
with the final text from the "done" event.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.tools.contracts import OnEvent
from app.tools.specialist.assessment.s7_presentation import guardrail
from app.tools.specialist.assessment.s7_presentation.prompts import ASSESSMENT_STYLE_PROMPT
from app.tools.structured_reply import render_structured_reply, render_template

logger = get_logger(__name__)

_CORRECTION = """

A previous draft of this reply was rejected because it did not match the \
result: {violations}. Use only the scores, years and dates given below, \
estimate no admission chances, and keep the verdict as given."""


def render(view: dict, user_message: str, on_event: OnEvent | None = None, depth: str | None = None,
           language: str | None = None, other_tools: tuple[str, ...] = ()) -> tuple[str, list[str]]:
    reply, sources = render_structured_reply(
        view, user_message, ASSESSMENT_STYLE_PROMPT, on_event=on_event, depth=depth, language=language,
        other_tools=other_tools,
    )
    violations = guardrail.check(reply, view, user_message)
    if not violations:
        return reply, sources

    logger.warning("assessment reply failed the guardrail, re-rendering: %s", violations)
    reply, sources = render_structured_reply(
        view, user_message, ASSESSMENT_STYLE_PROMPT + _CORRECTION.format(violations="; ".join(violations)),
        on_event=None, depth=depth, language=language, other_tools=other_tools,
    )
    violations = guardrail.check(reply, view, user_message)
    if not violations:
        return reply, sources

    logger.warning("assessment reply failed the guardrail twice, using the template: %s", violations)
    return render_template(view), sources
