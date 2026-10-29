"""
S7 — checks a rendered assessment against the render view it was written
from, deterministically. Anything the user's own message mentions may be
echoed.

  1. every score, year or other figure in the reply appears in the view
     (small whole numbers aside, unless written as a test score) — no
     invented minimums, scores or statistics;
  2. every month and year in the reply is one of the view's;
  3. no admission odds: no percentage, and no chance / probability /
     guarantee wording — the assessment never predicts admission;
  4. the verdict isn't contradicted: with a gap or an item to confirm, the
     reply may not say every requirement is met.
"""

from __future__ import annotations

import json
import re

_URL = re.compile(r"https?://\S+")
_TEST_SCORE = re.compile(r"(?:IELTS|TOEFL|GMAT|GRE|GATE|雅思|托福)\D{0,8}?(\d+(?:\.\d+)?)", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9])")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_ISO = re.compile(r"\b(20\d\d)-(\d{2})(?:-\d{2})?\b")
_ENGLISH_DATE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?(20\d\d)\b"
    r"|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(20\d\d)\b",
    re.IGNORECASE)
_CHINESE_DATE = re.compile(r"(20\d\d)\s*年\s*(\d{1,2})\s*月")
_ODDS = re.compile(
    # "Probability & statistics" is coursework the reply may list as a strength.
    r"\d\s?%|percent|\bodds\b|probabilit(?!y\s*(?:&|and)\s*stat)|\bchances?\b"
    r"|likely to (?:be )?(?:admitted|accepted|get in)|guarantee"
    r"|录取(?:概率|几率|可能性|机会)|概率|几率|成功率|胜算|保证录取|稳录|有戏",
    re.IGNORECASE)
_ALL_MET = re.compile(r"meet(?:s)? (?:all|every) (?:the )?(?:hard )?(?:requirements?|conditions?)"
                      r"|all (?:the )?(?:hard )?(?:requirements|conditions) (?:are )?met"
                      r"|全部(?:满足|符合)|都(?:满足|符合)了?(?:所有|全部)?(?:硬性)?(?:条件|要求)",
                      re.IGNORECASE)


def _numbers(text: str) -> set[float]:
    text = _URL.sub(" ", text)
    return {float(n) for n in _NUMBER.findall(text)}


def _months(text: str) -> set[tuple[int, int]]:
    found = {(int(y), int(m)) for y, m in _ISO.findall(text)}
    for m1, y1, m2, y2 in _ENGLISH_DATE.findall(text):
        month, year = (m1, y1) if m1 else (m2, y2)
        found.add((int(year), _MONTHS[month[:3].lower()]))
    found |= {(int(y), int(m)) for y, m in _CHINESE_DATE.findall(text)}
    return found


def check(reply: str, view: dict, user_message: str = "") -> list[str]:
    """One readable message per violation; empty when the reply is
    consistent with the view."""
    view_text = json.dumps(view, ensure_ascii=False, default=str)
    known_text = f"{view_text}\n{user_message}"
    violations: list[str] = []

    # Months and days written out in a date are covered by the date check.
    # Small whole numbers (counts, list numbering) are left alone, but not
    # a decimal (IELTS 7.5) or a number written as a test score (IELTS 7).
    known = _numbers(known_text) | {float(m) for _, m in _months(known_text)}
    scores = {float(n) for n in _TEST_SCORE.findall(reply)}
    unsupported = sorted(n for n in _numbers(reply)
                         if (n > 10 or not n.is_integer() or n in scores) and n not in known)
    if unsupported:
        violations.append("figures not in the result: " + ", ".join(f"{n:g}" for n in unsupported))

    invented = sorted(_months(reply) - _months(known_text))
    if invented:
        violations.append("dates not in the result: " + ", ".join(f"{y}-{m:02d}" for y, m in invented))

    odds = _ODDS.search(reply)
    if odds and not _ODDS.search(user_message):
        violations.append(f"admission-odds wording ({odds.group(0)!r}); the assessment predicts no admission")

    if view["verdict"]["status"] != "all_met" and _ALL_MET.search(reply):
        violations.append("says every requirement is met, but some are not met or still to confirm")
    return violations
