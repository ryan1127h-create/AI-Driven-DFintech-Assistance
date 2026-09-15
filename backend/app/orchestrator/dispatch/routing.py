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
    or more tool names to run — execution.py's run_tools() handles both the
    single-tool and multi-tool cases with the same code path).

    "decline" is checked first and short-circuits everything else: this
    assistant's whole purpose is the NUS MSc DFT programme (see
    classification.py's INTENT_CLASSIFIER_PROMPT), so a message classified
    off_topic never reaches a tool or even a generation call — the reply is
    a fixed string, which is also cheaper and more reliably on-scope than
    asking an LLM to decline politely every time.

    "off_topic" only forces a decline when it's the ONLY thing the
    classifier returned. Its own prompt promises never to combine
    off_topic with a genuine in-scope intent, but that promise is enforced
    by an instruction to the LLM, not by this code — if it's ever violated
    (a mixed message misjudged as partly off-topic), the in-scope
    intent(s) are still worth answering rather than discarding the whole
    turn over one classifier mistake."""
    valid = [i for i in intents if i in classification.VALID_INTENTS and i != "off_topic"]
    if "off_topic" in intents and not valid:
        return "decline", []
    if not valid:
        return "general", []

    if len(valid) == 1:
        name = tool_name_for(valid[0])
        return ("tools", [name]) if name else ("general", [])

    fanout_names = [n for n in (tool_name_for(i) for i in valid if i in classification.FANOUT_INTENTS) if n]
    if len(fanout_names) >= 2:
        return "tools", fanout_names
    if fanout_names:
        return "tools", fanout_names[:1]
    return "general", []
