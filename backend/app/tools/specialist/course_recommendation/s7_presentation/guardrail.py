"""
S7 — checks a rendered reply against the render view it was written from.
The rendering model is told never to invent or alter a course code or a
unit count; this verifies it didn't, deterministically.

Two checks:
  1. every course code in the reply appears somewhere in the view (a
     recommended course, a completed one named in degree progress, or one
     a note mentions) or in the user's own message;
  2. a unit count written right after a recommended course's code (before
     the next code or line break) matches that course's units.
"""

from __future__ import annotations

import json
import re

from app.tools.specialist.course_recommendation.s7_presentation.payload import course_units

_CODE = re.compile(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b")
_UNITS = re.compile(r"(\d+)\s*(?:units?|MCs?|学分)", re.IGNORECASE)
# How far after a course code a unit count is taken to belong to it.
_UNITS_WINDOW = 60


def check(reply: str, view: dict, user_message: str = "") -> list[str]:
    """Returns one readable message per violation; empty when the reply is
    consistent with the view. Codes the user typed may be echoed too (e.g.
    "FT5003 is left out, as you asked")."""
    known_codes = set(_CODE.findall(json.dumps(view, ensure_ascii=False)))
    known_codes |= set(_CODE.findall(user_message.upper()))
    units = course_units(view)
    violations: list[str] = []

    matches = list(_CODE.finditer(reply))
    unknown = sorted({m.group() for m in matches} - known_codes)
    if unknown:
        violations.append("course codes not in the result: " + ", ".join(unknown))

    for index, match in enumerate(matches):
        code = match.group()
        if code not in units:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(reply)
        segment = reply[match.end():min(end, match.end() + _UNITS_WINDOW)].split("\n", 1)[0]
        stated = _UNITS.search(segment)
        if stated and int(stated.group(1)) != units[code]:
            violations.append(f"{code} is {units[code]} units, the reply says {stated.group(1)}")

    return violations
