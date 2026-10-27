"""
Localization stage — the last step of every turn: makes sure the finished
answer is in the language the user is answered in (TurnState.reply_language,
resolved once per turn by turn_service.py from the classifier's detection
and the user's preference).

Answers are already written in that language: the generation steps
(knowledge Q&A, rendered structured replies, general chat) carry the reply-language line from app/core/reply_language.py,
so what streams to the user is in the right language from the first token.
This stage is the safety net for what wasn't: the fixed English replies (a
decline, an error, a request for missing input, a fallback), a generation
that ignored the instruction, and the specialists not yet given the line.

Whether a conversion happens is decided in code (reply_language.matches()),
never by an LLM: a reply already in the right language costs nothing. A
conversion that changes any figure is discarded — the English answer, whose
figures the specialists checked, is kept instead.

Not a registered Tool — see evaluation.py's module docstring for why these
orchestration-internal stages are plain functions instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.adapters.deepseek_adapter import llm
from app.core import reply_language
from app.core.config import settings
from app.core.logging import get_logger
from app.tools.contracts import OnEvent, ToolAnswer

logger = get_logger(__name__)

_LOCALIZE_PROMPT = """\
Rewrite the assistant reply given below in {language} for a university \
programme assistant chatbot. This is a language conversion, not a summary \
or a rewrite of the content — keep every claim, hedge, and piece of advice \
exactly as strong or as soft as it was.

Preserve EXACTLY as-is, character for character — do not translate, \
reformat, recalculate, or reword any of these:
- Numbers, dates, fee amounts, and deadlines.
- Course codes (e.g. "FT5005") and programme/university names.
- URLs and the "Sources:" section at the end, if present.
- The Markdown structure (headings, bullet lists, bold text).

Match the tone and formality of the user's own message given below — do \
not default to a more formal or more casual register than they used.

Respond with ONLY the rewritten text — no preamble, no explanation, no \
notes about what you changed."""

_URL = re.compile(r"https?://\S+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class LocalizeInput:
    reply_language: str
    user_message: str
    answer: ToolAnswer


def _figures(text: str) -> set[float]:
    """The amounts, years, scores and percentages in a text (URLs left
    out), thousands separators removed so S$76,409 and 76409 compare
    equal. Whole numbers up to 31 are left out: a translated date gains or
    loses them ("31 January 2027" -> "2027年1月31日")."""
    found = set()
    for token in _NUMBER.findall(_URL.sub(" ", text)):
        token = re.sub(r",(?=\d{3}\b)", "", token)
        try:
            value = float(token.replace(",", "."))
        except ValueError:
            continue
        if value > 31 or not value.is_integer():
            found.add(value)
    return found


def localize(inp: LocalizeInput, on_event: OnEvent | None = None) -> ToolAnswer:
    """Returns inp.answer unchanged when it is already in the reply
    language (the common case, no LLM call), the language is English or
    unset, or the setting is off. Otherwise makes one LLM call and returns
    a new ToolAnswer with only `.text` replaced. Never raises: a failed or
    empty conversion, or one that changed a figure, falls back to the
    original text — an answer in the wrong language is a smaller failure
    than a wrong figure or no reply at all."""
    code = (inp.reply_language or "en").strip().lower()
    text = inp.answer.text
    if code in ("en", "english", "") or not settings.enable_localization or not text:
        if text and not reply_language.matches(text, "en"):
            logger.warning("reply is not in English although English was asked for")
        return inp.answer
    if reply_language.matches(text, code):
        return inp.answer

    language = reply_language.name(code)
    try:
        payload = (
            f"User's message (for tone only, not to be answered again):\n{inp.user_message}\n\n"
            f"Text to rewrite into {language}:\n{text}"
        )
        rewritten = llm.complete(_LOCALIZE_PROMPT.format(language=language), payload,
                                 temperature=0, max_tokens=4096).strip()
    except Exception:
        logger.exception("converting the reply to %s failed, returning it as written", language)
        return inp.answer
    if not rewritten:
        return inp.answer
    if _figures(rewritten) != _figures(text):
        logger.warning("the %s conversion changed a figure, returning the reply as written", language)
        return inp.answer
    return replace(inp.answer, text=rewritten)
