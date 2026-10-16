"""
The quick-fill card shapes (see ToolAnswer.card / supplement_card): plain
data built from MissingInputField items, with no data access — so a tool's
presentation layer can offer a card without reaching the profile.
"""

from __future__ import annotations

from app.tools.contracts import MissingInputField

# The most supplementary fields offered under one answer, and the card's line.
MAX_SUPPLEMENTARY = 2
SUPPLEMENTARY_REASON = "A couple more details would help me tailor this to you (optional)."


def supplement_card(items: list[MissingInputField], reason: str = SUPPLEMENTARY_REASON) -> dict | None:
    """The non-blocking quick-fill card under an answer, for at most
    MAX_SUPPLEMENTARY profile fields (see ToolAnswer.supplement_card); None
    when none of `items` is a profile field. Built by the orchestrator's
    requirements gate from the tools' input_needs, or by a tool itself when
    only it knows, after reading the message, which fields are still open."""
    fields = [item for item in items if item.field_key][:MAX_SUPPLEMENTARY]
    if not fields:
        return None
    return {"kind": "quick_fill", "level": "supplementary", "reason": reason,
            "fields": [{"slot": i.slot, "field_key": i.field_key, "prompt": i.prompt} for i in fields]}
