"""
Routing stage — decides, from already-classified intents, whether the turn
declines (out of scope), falls back to plain conversation, or dispatches
to one or more matched tools. Never names a specific tool itself, only
ever looks one up by intent (see app/tools/registration.py) — a new
specialist becomes reachable here the moment it registers a Tool with the
right trigger_intents.
"""

from __future__ import annotations

from app.orchestrator import classification
from app.tools import contracts


def tool_name_for(intent: str) -> str | None:
    matches = contracts.registry.list_by_intent(intent)
    return matches[0].name if matches else None


def route(intents: list[str]) -> tuple[str, list[str]]:
    """Returns (mode, tool_names): "decline" (out of scope, no tool, no LLM
    call), "general" (no tool matched, plain conversation), or "tools" (1
    or more tool names to run, in classification order — execution.py's
    run_tools() handles the single-tool and multi-tool cases).

    "decline" is checked first and short-circuits everything else: this
    assistant's whole purpose is the NUS MSc DFT programme (see
    classification.py's INTENT_CLASSIFIER_PROMPT), so a message classified
    off_topic never reaches a tool or even a generation call — the reply is
    a fixed string, which is also cheaper and more reliably on-scope than
    asking an LLM to decline politely every time.

    "off_topic" and "general" only count when nothing in scope came with
    them: the classifier is told to return them alone, but if it pairs one
    with a real intent, that intent is still answered rather than the turn
    being lost to one classifier mistake. Every in-scope intent with a
    tool runs — a personalised one (course recommendation, the assessment)
    alongside a factual one ("which electives for AI, and the tuition?")
    included."""
    in_scope = [i for i in intents if i in classification.VALID_INTENTS and i not in ("off_topic", "general")]
    names = list(dict.fromkeys(n for n in (tool_name_for(i) for i in in_scope) if n))
    if names:
        return "tools", names
    if "off_topic" in intents and not in_scope and "general" not in intents:
        return "decline", []
    return "general", []
