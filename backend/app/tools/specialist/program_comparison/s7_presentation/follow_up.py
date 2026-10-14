"""
S7 — what this turn leaves for the next one (ToolAnswer.contexts, read
back as TurnState.previous_turn), and what the previous one left for
this.

An explore ends by inviting the user to pick programmes to compare, so it
records the programmes shown as that question's options: next turn, "HKU"
or "the first two" is read as the pick (by S1, given options_offered()).
A compare or detail records the programmes it covered, so "and the
deadlines?" stays on them. Pure functions over the domain result and the
previous turn.
"""

from __future__ import annotations

from app.tools.turn_context import PreviousTurn

TOOL = "comparison"


def _label(p: dict) -> str:
    return f"{p['university_short']} {p['short_name']}"


def turn_context(result: dict) -> dict:
    awaiting = None
    if result["mode"] == "explore":
        subjects = [p["program_id"] for p in result["matches"]]
        if result["matches"]:
            awaiting = {"kind": "choose_programs",
                        "options": [{"key": p["program_id"], "label": _label(p)} for p in result["matches"]]}
    else:
        subjects = [p["program_id"] for p in (result["baseline"], *result["subjects"])]
    return {"tool": TOOL, "mode": result["mode"], "subjects": subjects, "awaiting": awaiting}


def _context(previous: PreviousTurn | None) -> dict:
    return (previous.context_for(TOOL) if previous else None) or {}


def options_offered(previous: PreviousTurn | None) -> list[dict] | None:
    """The programmes the previous comparison reply offered to choose
    from, if it asked."""
    awaiting = _context(previous).get("awaiting") or {}
    return awaiting.get("options") if awaiting.get("kind") == "choose_programs" else None


def programs_covered(previous: PreviousTurn | None) -> list[str]:
    """The programmes the previous compare or detail covered (program
    ids, MSc DFT included) — what a follow-up without names is about."""
    context = _context(previous)
    return list(context.get("subjects") or []) if context.get("mode") in ("compare", "detail") else []
