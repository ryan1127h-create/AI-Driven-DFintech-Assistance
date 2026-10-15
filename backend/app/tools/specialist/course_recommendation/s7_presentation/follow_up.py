"""
S7 — what this turn leaves for the next one (ToolAnswer.contexts, read
back as TurnState.previous_turn): the mode and the courses recommended as
top picks. The next turn's intent classifier sees it, so a short
follow-up ("and the next semester?", "not that one") stays a course
question. The reply asks nothing, so nothing is awaited.

Pure function over the domain result.
"""

from __future__ import annotations

TOOL = "course_recommendation"


def turn_context(result: dict) -> dict:
    picks = [
        rec["course_code"]
        for group in result.get("groups", [])
        for rec in group.get("recommendations", [])
        if rec.get("recommended")
    ]
    return {"tool": TOOL, "mode": result.get("mode"), "subjects": list(dict.fromkeys(picks)), "awaiting": None}
