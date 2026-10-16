"""
S7 — renders the domain result into the chat reply.

Streams a reply from the render view (payload.py) under the mode's style
prompt, then checks it against that view (guardrail.py). A reply that
fails the check is rendered once more, silently, with the violations
spelled out; if that still fails, the deterministic template reply is
used instead. The streamed first draft is never left standing: the client
replaces it with the final text from the "done" event.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.tools.contracts import OnEvent
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched
from app.tools.specialist.career_planning.s7_presentation import guardrail
from app.tools.specialist.career_planning.s7_presentation.payload import to_render_view
from app.tools.specialist.career_planning.s7_presentation.prompts import EXPLORATION_REPEAT_STYLE_PROMPT, STYLES
from app.tools.structured_reply import render_structured_reply, render_template

logger = get_logger(__name__)

_CORRECTION = """

A previous draft of this reply was rejected because it did not match the \
result: {violations}. Use only the roles, course codes and dates given \
below, and no money figures."""


def render(
    result: dict, prefetched: Prefetched, user_message: str,
    on_event: OnEvent | None = None, depth: str | None = None, language: str | None = None,
    repeat: bool = False,
) -> tuple[str, list[str]]:
    """`repeat`: the result is the one the previous reply already gave
    (see follow_up.repeats_previous) — said briefly, not walked through."""
    view = to_render_view(result, prefetched)
    style = EXPLORATION_REPEAT_STYLE_PROMPT if repeat else STYLES[view["mode"]]
    role_names = [r["name"] for r in prefetched.role_catalog]

    reply, sources = render_structured_reply(view, user_message, style, on_event=on_event, depth=depth, language=language)
    violations = guardrail.check(reply, view, user_message, role_names)
    if not violations:
        return reply, sources

    logger.warning("career planning reply failed the guardrail, re-rendering: %s", violations)
    prompt = style + _CORRECTION.format(violations="; ".join(violations))
    reply, sources = render_structured_reply(view, user_message, prompt, on_event=None, depth=depth, language=language)
    violations = guardrail.check(reply, view, user_message, role_names)
    if not violations:
        return reply, sources

    logger.warning("career planning reply failed the guardrail twice, using the template: %s", violations)
    return render_template(view), sources
