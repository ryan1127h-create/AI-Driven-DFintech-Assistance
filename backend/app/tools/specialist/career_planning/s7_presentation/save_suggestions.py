"""
S7 — profile facts the user stated this turn that their profile doesn't
hold yet, offered under the reply for saving (see ToolAnswer
.save_suggestions): the role they plan for, the roles they compare, when
they'll look for work, their internship status and where they want to
work. Only what the message itself said is offered.

Pure function: it compares what S1 parsed with what S2 prefetched.
"""

from __future__ import annotations

from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched


def save_suggestions(parsed: ParsedCareerRequest, prefetched: Prefetched, mode: str) -> list[dict]:
    facts = prefetched.facts
    suggestions: list[dict] = []

    if parsed.roles:
        if mode == "plan" and parsed.roles[0] != facts.get("main_target_role"):
            suggestions.append({"field_key": "main_target_role", "value": parsed.roles[0]})
        known = list(facts.get("target_role_families") or [])
        new = [r for r in parsed.roles if r not in known]
        if mode == "compare" and new:
            suggestions.append({"field_key": "target_role_families", "value": [*known, *new]})

    for field_key in ("job_search_timeline", "internship_status"):
        value = getattr(parsed, field_key)
        if value and value != facts.get(field_key):
            suggestions.append({"field_key": field_key, "value": value})

    markets = list(facts.get("target_markets") or [])
    new_markets = [m for m in parsed.target_markets if m not in markets]
    if new_markets:
        suggestions.append({"field_key": "target_markets", "value": [*markets, *new_markets]})
    return suggestions
