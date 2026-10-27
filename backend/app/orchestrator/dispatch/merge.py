"""
Merge stage — joins the evaluated drafts of a multi-tool turn into one
reply: each draft in classification order, separated by a rule, with a
later draft's paragraphs that repeat an earlier one left out. No LLM
call: every draft is already written in the reply language and checked by
its own specialist (figures, dates, names), and rewriting them into one
flowing text would put those checked figures back in an LLM's hands with
nothing checking them afterwards.

Not a registered Tool — see evaluation.py's module docstring for why these
orchestration-internal stages are plain functions instead.
"""

from __future__ import annotations

import re

from app.tools.contracts import ToolAnswer

_SEPARATOR = "\n\n---\n\n"
# A later draft's paragraph is dropped as a repeat when it is at least this
# long and this share of its words already appear in one earlier paragraph
# (each draft is written from the whole message, so two of them sometimes
# explain the same step, e.g. the Student's Pass under admissions and fees).
_MIN_REPEAT_CHARS = 120
_REPEAT_OVERLAP = 0.75
_WORD = re.compile(r"[^\W_]{3,}")


def _words(paragraph: str) -> set[str]:
    return set(_WORD.findall(paragraph.lower()))


def _is_repeat(paragraph: str, earlier: list[set[str]]) -> bool:
    if len(paragraph) < _MIN_REPEAT_CHARS:
        return False
    words = _words(paragraph)
    return bool(words) and any(len(words & seen) / len(words) >= _REPEAT_OVERLAP for seen in earlier)


def _without_repeats(texts: list[str]) -> list[str]:
    """Each draft minus the paragraphs an earlier draft already said; a
    draft left with nothing is dropped. Headings and short lines stay."""
    seen: list[set[str]] = []
    kept_texts = []
    for text in texts:
        paragraphs = re.split(r"\n\s*\n", text)
        kept = [p for p in paragraphs if not _is_repeat(p, seen)]
        seen.extend(_words(p) for p in paragraphs if len(p) >= _MIN_REPEAT_CHARS)
        if any(p.strip() for p in kept):
            kept_texts.append("\n\n".join(kept).strip())
    return kept_texts


def merge(partials: list[tuple[str, ToolAnswer]]) -> ToolAnswer:
    """`partials`: (tool name, answer) pairs in classification order. The
    text (less paragraphs an earlier draft already said), sources, save
    suggestions and turn contexts of every draft are kept, in order; the
    first card any draft carries rides on the reply. The merged reply asks
    for clarification only when every draft does."""
    texts = _without_repeats([answer.text.strip() for _, answer in partials if answer.text and answer.text.strip()])
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
