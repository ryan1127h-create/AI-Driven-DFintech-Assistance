"""
S7 — renders the domain result into the chat reply.

Streams a reply from the render view (payload.py), then checks it against
that view (guardrail.py). A reply that fails the check is rendered once
more, silently, with the violations spelled out; if that still fails, the
deterministic template reply is used instead. The streamed first draft is
never left standing: the client replaces it with the final text from the
"done" event.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.tools.contracts import OnEvent
from app.tools.specialist.course_recommendation.s7_presentation import guardrail
from app.tools.specialist.course_recommendation.s7_presentation.payload import to_render_view
from app.tools.specialist.course_recommendation.s7_presentation.prompts import (
    AD_HOC_STYLE_PROMPT,
    COURSE_RECOMMENDATION_STYLE_PROMPT,
)
from app.tools.structured_reply import render_structured_reply, render_template

logger = get_logger(__name__)

_CORRECTION = """

A previous draft of this reply was rejected because it did not match the \
result: {violations}. Use only the course codes and unit counts given below."""


def render(
    result: dict, user_message: str, on_event: OnEvent | None = None, depth: str | None = None,
) -> tuple[str, list[str]]:
    view = to_render_view(result)
    style = AD_HOC_STYLE_PROMPT if view["mode"] == "ad_hoc" else COURSE_RECOMMENDATION_STYLE_PROMPT
    reply, sources = render_structured_reply(view, user_message, style, on_event=on_event, depth=depth)
    violations = guardrail.check(reply, view, user_message)
    if not violations:
        return reply, sources

    logger.warning("course recommendation reply failed the guardrail, re-rendering: %s", violations)
    prompt = style + _CORRECTION.format(violations="; ".join(violations))
    reply, sources = render_structured_reply(view, user_message, prompt, on_event=None, depth=depth)
    violations = guardrail.check(reply, view, user_message)
    if not violations:
        return reply, sources

    logger.warning("course recommendation reply failed the guardrail twice, using the template: %s", violations)
    return render_template(view), sources
