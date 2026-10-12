"""
Requirements gate — runs after routing.py decides which tool(s) to call
and before execution.py invokes any of them. Collects every matched tool's
declared input_needs for the current TurnState and sorts them by level
(see app/tools/contracts.py MissingInputField):

  - required, and optional ones the user hasn't declined this session,
    block the turn: NONE of the tools run, and the turn is answered with
    one consolidated request (and a card) for what's missing. Only the
    optional ones may be skipped; skipping re-sends the message with them
    declined.
  - supplementary ones never block: the tools run, and up to
    MAX_SUPPLEMENTARY of them are offered in a card under the answer.

Blocking is all-or-nothing over the WHOLE batch routing.py matched, not
per tool: letting some tools spend a real domain/LLM call while another is
already known to be short wastes that work and produces a reply that's
part answer, part clarifying question — worse for the user than asking
once, up front, for everything still missing.

Pure code, no LLM call, and never raises: a tool's own input_needs check
failing (e.g. a transient profile lookup error) is treated as "needs
nothing" for that tool rather than blocking the turn over an unrelated
internal error — the same fail-open discipline
knowledge_retrieval.retrieve() and evaluate_branch() already follow.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.tools import contracts
from app.tools.contracts import MissingInputField, ToolAnswer
from app.tools.turn_context import TurnState

logger = get_logger(__name__)


# The most supplementary fields offered under one answer.
MAX_SUPPLEMENTARY = 2

_SUPPLEMENTARY_REASON = "A couple more details would help me tailor this to you (optional)."


@dataclass(frozen=True)
class RequirementsResult:
    ready: bool
    # What blocks the turn (required, and optional not declined).
    missing: tuple[MissingInputField, ...] = ()
    # What may be offered under the answer.
    supplementary: tuple[MissingInputField, ...] = ()


def _declined(item: MissingInputField, state: TurnState) -> bool:
    return item.level != "required" and (item.field_key or item.slot) in state.declined_fields


def check_requirements(tool_names: list[str], state: TurnState) -> RequirementsResult:
    """Collects every matched tool's input needs, de-duplicated by slot (two
    tools needing the same field — e.g. a target role — are asked about
    only once, at the stricter of their levels), minus what the user has
    declined this session."""
    if not settings.enable_input_requirements_gate:
        return RequirementsResult(ready=True)

    strictness = {"required": 0, "optional": 1, "supplementary": 2}
    needs: dict[str, MissingInputField] = {}
    for name in tool_names:
        tool = contracts.registry.get(name)
        if tool.input_needs is None:
            continue
        try:
            for item in tool.input_needs(state):
                known = needs.get(item.slot)
                if known is None or strictness[item.level] < strictness[known.level]:
                    needs[item.slot] = item
        except Exception as exc:
            logger.warning(
                "input_needs check failed for tool=%s, treating as satisfied — %s", name, exc
            )
    open_needs = [item for item in needs.values() if not _declined(item, state)]
    missing = tuple(item for item in open_needs if item.level != "supplementary")
    supplementary = tuple(item for item in open_needs if item.level == "supplementary")
    return RequirementsResult(ready=not missing, missing=missing, supplementary=supplementary)


def build_need_input_answer(result: RequirementsResult) -> ToolAnswer:
    """Deterministic, LLM-free reply listing what's still needed — no
    domain/agent call has run yet, so there is nothing to evaluate or
    synthesize. A single missing field reuses that tool's own prompt text
    verbatim (byte-identical to the old single-tool clarify wording); 2+
    missing fields are listed as short bullet points. The missing fields a
    profile field can answer also come back as a quick-fill card (see
    ToolAnswer.card); the text stays as the reply either way, for the
    conversation history and for a client that shows no card."""
    if len(result.missing) == 1:
        text = result.missing[0].prompt
    else:
        text = "Before I can help with that, I need a bit more information:\n" + "\n".join(
            f"- {item.prompt}" for item in result.missing
        )
    return ToolAnswer(
        text=text, agent_used="orchestrator_need_input", needs_clarification=True,
        card=_blocking_card(result.missing, text),
    )


def _fields(items) -> list[dict]:
    return [{"slot": item.slot, "field_key": item.field_key, "prompt": item.prompt} for item in items]


def _blocking_card(missing: tuple[MissingInputField, ...], reason: str) -> dict | None:
    """A consent card when the profile can't be used without one (the
    fields couldn't be read anyway); otherwise a quick-fill card for the
    profile fields, skippable only when none of them is required."""
    consent = next((item for item in missing if item.consent_key), None)
    if consent is not None:
        return {"kind": "consent", "consent_key": consent.consent_key, "reason": consent.prompt}
    fields = [item for item in missing if item.field_key]
    if not fields:
        return None
    required = any(item.level == "required" for item in missing)
    return {
        "kind": "quick_fill",
        "level": "required" if required else "optional",
        "skippable": not required,
        "reason": reason,
        "fields": _fields(fields),
    }


def build_supplement_card(result: RequirementsResult) -> dict | None:
    """The non-blocking card under an answer: at most MAX_SUPPLEMENTARY
    supplementary profile fields."""
    fields = [item for item in result.supplementary if item.field_key][:MAX_SUPPLEMENTARY]
    if not fields:
        return None
    return {"kind": "quick_fill", "level": "supplementary", "reason": _SUPPLEMENTARY_REASON, "fields": _fields(fields)}
