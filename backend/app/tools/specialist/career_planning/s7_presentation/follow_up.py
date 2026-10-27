"""
S7 — what this turn leaves for the next one (ToolAnswer.contexts, read
back as TurnState.previous_turn), and what the previous one left for
this.

An exploration ends by asking the student to pick a role, so it records
the roles shown as that question's options: next turn, "software
engineering" or "the second one" is read as the pick (by the classifier,
and by S1 given options_offered()). A plan or comparison records the
roles it covered and asks nothing.

Pure functions over the domain result and the previous turn.
"""

from __future__ import annotations

from app.tools.turn_context import PreviousTurn

TOOL = "career"


def turn_context(result: dict) -> dict:
    roles = [fit["role"] for fit in result["roles"]]
    awaiting = None
    if result["mode"] == "exploration" and roles:
        awaiting = {"kind": "choose_role", "options": [{"key": r["tag"], "label": r["name"]} for r in roles]}
    return {"tool": TOOL, "mode": result["mode"], "subjects": [r["tag"] for r in roles], "awaiting": awaiting}


def options_offered(previous: PreviousTurn | None) -> list[dict] | None:
    """The roles the previous career reply asked the student to choose
    from, if it asked."""
    context = previous.context_for(TOOL) if previous else None
    awaiting = (context or {}).get("awaiting") or {}
    return awaiting.get("options") if awaiting.get("kind") == "choose_role" else None


def roles_covered(previous: PreviousTurn | None) -> list[str]:
    """The roles the previous career reply covered (role tags), if any —
    what "and compared with X?" compares against."""
    context = previous.context_for(TOOL) if previous else None
    return list((context or {}).get("subjects") or [])


def repeats_previous(result: dict, previous: PreviousTurn | None) -> bool:
    """An exploration showing exactly the roles the previous one did: the
    reply should say so briefly instead of walking through them again."""
    context = previous.context_for(TOOL) if previous else None
    return bool(
        context and context.get("mode") == "exploration" and result["mode"] == "exploration"
        and context.get("subjects") == [fit["role"]["tag"] for fit in result["roles"]]
    )
