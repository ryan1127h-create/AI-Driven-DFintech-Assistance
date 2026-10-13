"""
S7 — checks a rendered reply against the render view it was written
from. The rendering model is told never to invent courses, roles, dates or
money; this verifies it didn't, deterministically.

Four checks (anything the user's own message mentions may be echoed):
  1. every course code in the reply appears in the view;
  2. no role family the view doesn't mention is named (by its English name);
  3. every month-and-year in the reply is one of the view's dates' months;
  4. no money amount or salary figure appears — the data has none.
"""

from __future__ import annotations

import json
import re

_CODE = re.compile(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_ISO = re.compile(r"\b(20\d\d)-(\d{2})(?:-\d{2})?\b")
_ENGLISH = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?(20\d\d)\b",
    re.IGNORECASE)
_CHINESE = re.compile(r"(20\d\d)\s*年\s*(\d{1,2})\s*月")
_MONEY = re.compile(
    r"(?:S?\$|SGD|USD|RMB|HKD|¥|￥|€|£)\s?\d"
    r"|\d[\d,.]*\s?(?:k|K)?\s?(?:SGD|USD|RMB|HKD|元|新币|美元)"
    r"|(?:salary|salaries|pay|薪资|薪水|年薪|月薪|工资)[^\n]{0,20}?\d",
    re.IGNORECASE)


def _months(text: str) -> set[tuple[int, int]]:
    found = {(int(y), int(m)) for y, m in _ISO.findall(text)}
    found |= {(int(y), _MONTHS[m[:3].lower()]) for m, y in _ENGLISH.findall(text)}
    found |= {(int(y), int(m)) for y, m in _CHINESE.findall(text)}
    return found


def check(reply: str, view: dict, user_message: str = "", role_names: list[str] | tuple[str, ...] = ()) -> list[str]:
    """One readable message per violation; empty when the reply is
    consistent with the view. `role_names`: every role family's name."""
    view_text = json.dumps(view, ensure_ascii=False, default=str)
    violations: list[str] = []

    known_codes = set(_CODE.findall(view_text)) | set(_CODE.findall(user_message.upper()))
    unknown = sorted(set(_CODE.findall(reply)) - known_codes)
    if unknown:
        violations.append("course codes not in the result: " + ", ".join(unknown))

    # A role's name may also be a skill's ("data analytics"): only a name
    # the view doesn't mention at all, written as the role's proper name,
    # counts as stray.
    lowered_view, lowered_message = view_text.lower(), user_message.lower()
    stray = sorted(
        name for name in role_names
        if name.lower() not in lowered_view and name.lower() not in lowered_message
        and re.search(rf"\b{re.escape(name)}\b", reply)
    )
    if stray:
        violations.append("roles not in the result: " + ", ".join(stray))

    allowed = _months(view_text) | _months(user_message)
    invented = sorted(_months(reply) - allowed)
    if invented:
        violations.append("dates not in the result: " + ", ".join(f"{y}-{m:02d}" for y, m in invented))

    if _MONEY.search(reply) and not _MONEY.search(user_message):
        violations.append("a money or salary figure, which the result has none of")
    return violations
