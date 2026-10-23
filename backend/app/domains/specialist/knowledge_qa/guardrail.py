"""
Checks a knowledge answer's figures against what it was given: every
amount, percentage, score, date and other number in the reply must appear
in the reference material or the current facts (or the user's own
message), or be the result of one simple calculation on two such numbers
that the reply itself states — a sum, difference, product or quotient, or
a percentage of or off an amount ("40% of S$76,409 is S$30,563.60"),
rounded to the cent or the whole number. Requiring the operands in the
reply keeps a stale figure from passing as some accidental combination of
the sources' numbers. Anything else was made up, or carried over from the
model's own memory of an earlier year.

Small whole numbers (0-10) are left alone — counts, list numbering and
"2 referees" style wording, too common to judge — and so are digits inside
codes (FT5005), academic years (AY2027/28) and URLs.
"""

from __future__ import annotations

import re

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december")
_URL = re.compile(r"https?://\S+")
_ACADEMIC_YEAR = re.compile(r"\bAY\s?\d{4}/\d{2,4}\b", re.IGNORECASE)
# A number not glued to letters on either side (FT5005, AY2027, 2nd stay out).
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z0-9])"
                     r"|(?<![A-Za-z0-9.,])\d+(?:\.\d+)?(?![A-Za-z0-9])")
_DAY_MONTH = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)
_MONTH_DAY = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b", re.IGNORECASE)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _numbers(text: str) -> set[float]:
    text = _ACADEMIC_YEAR.sub(" ", _URL.sub(" ", text))
    found = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(float(token.replace(",", "")))
        except ValueError:
            continue
    # Dates written as numbers (2027-01-31) also stand for their parts.
    for year, month, day in _ISO_DATE.findall(text):
        found |= {float(year), float(int(month)), float(int(day))}
    return found


def _days(text: str) -> set[tuple[str, int]]:
    days = {(m.lower(), int(d)) for d, m in _DAY_MONTH.findall(text)}
    days |= {(m.lower(), int(d)) for m, d in _MONTH_DAY.findall(text)}
    for _year, month, day in _ISO_DATE.findall(text):
        days.add((_MONTHS[int(month) - 1], int(day)))
    return days


def _derived(known: set[float]) -> set[float]:
    """Every result of one simple calculation on two known numbers, each
    kept both to the cent and to the whole number."""
    values = sorted(known)
    results: set[float] = set()
    for a in values:
        for b in values:
            candidates = [a + b, a - b, a * b, a * b / 100, a * (1 - b / 100)]
            if b:
                candidates.append(a / b)
            for v in candidates:
                results.add(round(v, 2))
                results.add(float(round(v)))
    return results


_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def drop_unsupported(reply: str, sources: str, user_message: str = "") -> tuple[str, int]:
    """The reply without the sentences check() would flag on their own, and
    how many were dropped. Lines are split into sentences; a sentence
    carrying a figure or date the sources don't support goes, the rest of
    the line stays."""
    kept_lines, dropped = [], 0
    for line in reply.split("\n"):
        sentences = _SENTENCE_END.split(line)
        kept = [s for s in sentences if not check(s, sources, user_message)]
        dropped += len(sentences) - len(kept)
        if kept or not line.strip():
            kept_lines.append(" ".join(kept))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip(), dropped


def check(reply: str, sources: str, user_message: str = "") -> list[str]:
    """What in `reply` the `sources` (reference material plus current facts)
    don't support; empty when everything checks out."""
    known_text = f"{sources}\n{user_message}"
    known = _numbers(known_text)
    problems = []
    in_reply = _numbers(reply)
    unsupported = [n for n in in_reply if n > 10 and n not in known]
    if unsupported:
        derived = _derived(known & in_reply)  # operands the reply states
        unsupported = [n for n in unsupported if round(n, 2) not in derived]
    unsupported.sort()
    if unsupported:
        problems.append("figures not in the reference material: " + ", ".join(f"{n:g}" for n in unsupported))
    wrong_days = sorted(_days(reply) - _days(known_text))
    if wrong_days:
        problems.append("dates not in the reference material: "
                        + ", ".join(f"{d} {m.capitalize()}" for m, d in wrong_days))
    return problems
