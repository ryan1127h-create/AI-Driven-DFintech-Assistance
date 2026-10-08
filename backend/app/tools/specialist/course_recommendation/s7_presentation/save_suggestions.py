"""
S7 — profile facts the user stated this turn that their profile doesn't
hold yet, offered under the reply for saving (see ToolAnswer
.save_suggestions). Only fields the user owns are offered: the target
role, Vertical interest, Capstone intent and study mode. School-record
fields (completed or planned courses, the declared Vertical) never are —
the school's record is the source for those.

Pure function: it compares what S1 parsed with what S2 prefetched.
"""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.specialist.course_recommendation.s2_assembly.prefetched import Prefetched


def save_suggestions(parsed: ParsedRequest, prefetched: Prefetched) -> list[dict]:
    facts = prefetched.facts
    suggestions: list[dict] = []

    role = prefetched.stated_role_tag
    if role and role != facts.get("main_target_role"):
        suggestions.append({"field_key": "main_target_role", "value": role})

    known = facts.get("track_interest") or []
    new = [t for t in parsed.vertical_preference if t not in known]
    if new:
        suggestions.append({"field_key": "track_interest", "value": [*known, *new]})

    for field_key in ("capstone_intent", "study_mode"):
        value = getattr(parsed, field_key)
        if value and value != facts.get(field_key):
            suggestions.append({"field_key": field_key, "value": value})
    return suggestions
