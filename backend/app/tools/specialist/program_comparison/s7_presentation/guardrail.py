"""
S7 — checks a rendered reply against the render view it was written from.
The rendering model is told never to invent or convert figures, bring in
other programmes or rank them; this verifies it didn't, deterministically.

Five checks (anything the user's own message mentions may be echoed):
  1. every amount written with a currency is a number in the view, and
     none is restated in 万 / k units;
  2. every month-and-year in the reply is one of the view's dates' months;
  3. no university the view doesn't cover is named (any of its names or
     aliases);
  4. every university the view does cover is named — a short follow-up
     ("the first one and HKU") can mislead the writer into dropping one;
  5. no ranking or verdict wording ("better than", "the best", "更好",
     "首选", ...).

The caveats rule (each conflicting official statement is mentioned) is
left to the prompt: it can't be checked reliably in every language.
"""

from __future__ import annotations

import json
import re

_CURRENCY = r"(?:SGD|HKD|GBP|USD|AUD|S\$|HK\$|US\$|A\$|\$|£|新币|新元|新加坡元|港币|港元|英镑|美元|澳元)"
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_AMOUNT = re.compile(rf"{_CURRENCY}\s?({_NUMBER})\s?(万|千|k|K|m|M)?|({_NUMBER})\s?(万|千|k|K|m|M)?\s?{_CURRENCY}")
_ANY_NUMBER = re.compile(_NUMBER)

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_ISO = re.compile(r"\b(20\d\d)-(\d{2})(?:-\d{2})?\b")
_ENGLISH_DATE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?(20\d\d)\b"
    r"|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d\d)\b",
    re.IGNORECASE)
_CHINESE_DATE = re.compile(r"(20\d\d)\s*年\s*(\d{1,2})\s*月")

_RANKING = re.compile(
    r"\bbetter than\b|\bthe best\b|\bbest (?:choice|option|programme|program|fit)\b|\bsuperior to\b"
    r"|\branked (?:higher|above|first)\b|\brecommend (?:you )?(?:choose|pick|go with)\b"
    r"|更好|更优|优于|最佳|首选|最好的(?:选择|项目)|排名|建议你选|推荐你选|更值得",
    re.IGNORECASE)


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in _ANY_NUMBER.findall(text)}


def _months(text: str) -> set[tuple[int, int]]:
    found = {(int(y), int(m)) for y, m in _ISO.findall(text)}
    for m1, y1, m2, y2 in _ENGLISH_DATE.findall(text):
        month, year = (m1, y1) if m1 else (m2, y2)
        found.add((int(year), _MONTHS[month[:3].lower()]))
    found |= {(int(y), int(m)) for y, m in _CHINESE_DATE.findall(text)}
    return found


def _mentions(text: str, name: str) -> bool:
    if re.search(r"[一-鿿]", name):
        return name in text
    return re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, re.IGNORECASE) is not None


def check(reply: str, view: dict, user_message: str = "", universities: list[dict] | tuple = ()) -> list[str]:
    """One readable message per violation; empty when the reply is
    consistent with the view. `universities`: every catalogue university,
    {short_name, name, aliases}."""
    view_text = json.dumps(view, ensure_ascii=False, default=str)
    violations: list[str] = []

    allowed = _numbers(view_text) | _numbers(user_message)
    bad_amounts, scaled = [], []
    for m in _AMOUNT.finditer(reply):
        number, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if unit:
            scaled.append(m.group(0).strip())
        elif float(number.replace(",", "")) not in allowed:
            bad_amounts.append(m.group(0).strip())
    if bad_amounts:
        violations.append("amounts not in the result: " + ", ".join(dict.fromkeys(bad_amounts)))
    if scaled:
        violations.append("amounts restated in other units: " + ", ".join(dict.fromkeys(scaled)))

    invented = sorted(_months(reply) - _months(view_text) - _months(user_message))
    if invented:
        violations.append("dates not in the result: " + ", ".join(f"{y}-{m:02d}" for y, m in invented))

    stray, left_out = [], []
    for u in universities:
        names = [n for n in (u["short_name"], u["name"], *u.get("aliases", [])) if n and len(n) >= 2]
        in_reply = any(_mentions(reply, n) for n in names)
        if any(_mentions(view_text, n) for n in names):
            if not in_reply:
                left_out.append(u["short_name"])
        elif in_reply and not any(_mentions(user_message, n) for n in names):
            stray.append(next(n for n in names if _mentions(reply, n)))
    if stray:
        violations.append("programmes not in the result: " + ", ".join(stray))
    if left_out:
        violations.append("programmes in the result left out of the reply: " + ", ".join(left_out))

    ranking = sorted({m.group(0) for m in _RANKING.finditer(reply)})
    if ranking:
        violations.append("ranking or verdict wording: " + ", ".join(ranking))
    return violations
