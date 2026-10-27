"""
The language a reply is written in (TurnState.reply_language, an ISO 639-1
code resolved per turn by orchestrator/turn_service.py) as one line for a
generation prompt, and a cheap code check of whether a finished reply is in
that language.

Answers are written in the reply language from the start, so what streams
to the user is already in it; dispatch/localization.py translates only a
reply that the check finds in another language (the fixed English replies,
or a generation that ignored the instruction).
"""

from __future__ import annotations

import re

NAMES = {
    "en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "fr": "French", "de": "German",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian", "nl": "Dutch", "ru": "Russian", "vi": "Vietnamese",
    "th": "Thai", "id": "Indonesian", "ms": "Malay", "hi": "Hindi", "ar": "Arabic", "tr": "Turkish",
}
_SCRIPT_NOTE = {
    "zh": " (in the script the user writes: Simplified or Traditional characters)",
}

_URL = re.compile(r"https?://\S+")
_CODE = re.compile(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b")
_LATIN = re.compile(r"[A-Za-z]")
_SCRIPTS = {
    "han": re.compile(r"[一-鿿㐀-䶿]"),
    "kana": re.compile(r"[぀-ヿ]"),
    "hangul": re.compile(r"[가-힯]"),
    "cyrillic": re.compile(r"[Ѐ-ӿ]"),
    "arabic": re.compile(r"[؀-ۿ]"),
    "thai": re.compile(r"[฀-๿]"),
    "devanagari": re.compile(r"[ऀ-ॿ]"),
}
# Which script a language's text is mostly written in.
_LANGUAGE_SCRIPT = {"zh": "han", "ja": "kana", "ko": "hangul", "ru": "cyrillic", "ar": "arabic",
                    "th": "thai", "hi": "devanagari"}
_ENGLISH_WORDS = {"the", "and", "is", "are", "you", "your", "to", "of", "for", "in", "with", "this", "that",
                  "be", "can", "will", "not", "on", "it", "as"}


def name(code: str | None) -> str | None:
    if not code:
        return None
    return NAMES.get(code.strip().lower(), code)


def instruction(code: str | None) -> str:
    """The line to add to a generation prompt. Without a resolved language,
    the reply follows the user's message."""
    language = name(code)
    if not language:
        return "Reply language: write the reply in the language of the user's message."
    note = _SCRIPT_NOTE.get(code.strip().lower(), "")
    return (f"Reply language: write the whole reply in {language}{note}, whatever language the material "
            "above is in. Keep course codes, programme and university names, URLs and every figure as given; "
            f"write dates the {language} way with the same day, month and year, and put every other English "
            f"phrase into {language} rather than leaving it in English.")


def with_instruction(prompt: str, code: str | None) -> str:
    return f"{prompt.rstrip()}\n\n{instruction(code)}\n"


def _letters(text: str) -> tuple[dict[str, int], int, list[str]]:
    """Counts of each script's characters, of Latin letters, and the Latin
    words — over the prose only (URLs and course codes left out)."""
    text = _CODE.sub(" ", _URL.sub(" ", text))
    counts = {script: len(pattern.findall(text)) for script, pattern in _SCRIPTS.items()}
    words = re.findall(r"[A-Za-z]+", text.lower())
    return counts, len(_LATIN.findall(text)), words


def matches(text: str, code: str | None) -> bool:
    """Whether `text` reads as written in `code`'s language. A judgement on
    scripts and common words, meant to catch a reply plainly in the wrong
    language (English to a Chinese user, Chinese to an English one) — not
    to tell close Latin-script languages apart, where it trusts the reply."""
    if not text.strip() or not code:
        return True
    code = code.strip().lower()
    counts, latin, words = _letters(text)
    script = _LANGUAGE_SCRIPT.get(code)
    if script == "kana":
        # Japanese mixes kana with Han characters; some kana is the tell.
        native = counts["kana"] + counts["han"]
        return counts["kana"] > 0 and native >= 0.25 * (native + latin)
    if script:
        native = counts[script]
        return native >= 0.25 * (native + latin)
    non_latin = sum(counts.values())
    if non_latin > 0.05 * (non_latin + latin):
        return False  # a Latin-script language, but the text is mostly in another script
    if code == "en" or not words:
        return True
    # Another Latin-script language: wrong only if it reads as English.
    english = sum(w in _ENGLISH_WORDS for w in words)
    return english < 0.08 * len(words)
