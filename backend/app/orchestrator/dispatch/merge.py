"""
Merge stage — joins the evaluated drafts of a multi-tool turn into one
reply: each draft in classification order, separated by a rule. No LLM
call: every draft is already written in the reply language and checked by
its own specialist (figures, dates, names), and rewriting them into one
flowing text would put those checked figures back in an LLM's hands with
nothing checking them afterwards.

Not a registered Tool — see evaluation.py's module docstring for why these
orchestration-internal stages are plain functions instead.
"""

from __future__ import annotations

from app.tools.contracts import ToolAnswer

_SEPARATOR = "\n\n---\n\n"


def merge(partials: list[tuple[str, ToolAnswer]]) -> ToolAnswer:
    """`partials`: (tool name, answer) pairs in classification order. The
    text, sources, save suggestions and turn contexts of every draft are
    kept, in order; the first card any draft carries rides on the reply.
    The merged reply asks for clarification only when every draft does."""
    texts = [answer.text.strip() for _, answer in partials if answer.text and answer.text.strip()]
    sources = list(dict.fromkeys(s for _, answer in partials for s in answer.sources))
    card = next((answer.card for _, answer in partials if answer.card), None)
    return ToolAnswer(
        text=_SEPARATOR.join(texts),
        sources=sources,
        agent_used="+".join(answer.agent_used or name for name, answer in partials),
        needs_clarification=all(answer.needs_clarification for _, answer in partials),
        card=card,
        save_suggestions=[s for _, answer in partials for s in answer.save_suggestions],
        contexts=[c for _, answer in partials for c in answer.contexts],
    )
