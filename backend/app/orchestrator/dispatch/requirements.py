"""
Requirements gate — runs after routing.py decides which tool(s) to call
and before execution.py invokes any of them. Checks every matched tool's
declared `required_input` against the current turn's TurnState; if even
one tool is missing something it needs, NONE of them are invoked this
turn — the turn is answered instead with one consolidated request for
whatever is still missing.

This is deliberately an all-or-nothing gate over the WHOLE batch routing.py
matched, not a per-tool decision: letting some tools spend a real
domain/LLM call while another is already known to be unanswerable wastes
that work and produces a reply that's part answer, part clarifying
question — worse for the user than asking once, up front, for everything
still missing.

Pure code, no LLM call, and never raises: a tool's own required_input
check failing (e.g. a transient profile lookup error) is treated as "not
missing anything" for that tool rather than blocking the turn over an
unrelated internal error — the same fail-open discipline
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


@dataclass(frozen=True)
class RequirementsResult:
    ready: bool
    missing: tuple[MissingInputField, ...] = ()


def check_requirements(tool_names: list[str], state: TurnState) -> RequirementsResult:
    """Collects every missing required field across all of tool_names,
    de-duplicated by slot (two tools requiring the same field — e.g. a
    target role — are asked about only once)."""
    if not settings.enable_input_requirements_gate:
        return RequirementsResult(ready=True)

    missing: dict[str, MissingInputField] = {}
    for name in tool_names:
        tool = contracts.registry.get(name)
        if tool.required_input is None:
            continue
        try:
            for item in tool.required_input(state):
                missing.setdefault(item.slot, item)
        except Exception as exc:
            logger.warning(
                "required_input check failed for tool=%s, treating as satisfied — %s", name, exc
            )
    return RequirementsResult(ready=not missing, missing=tuple(missing.values()))


def build_need_input_answer(result: RequirementsResult) -> ToolAnswer:
    """Deterministic, LLM-free reply listing what's still needed — no
    domain/agent call has run yet, so there is nothing to evaluate or
    synthesize. A single missing field reuses that tool's own prompt text
    verbatim (byte-identical to the old single-tool clarify wording); 2+
    missing fields are listed as short bullet points."""
    if len(result.missing) == 1:
        text = result.missing[0].prompt
    else:
        text = "Before I can help with that, I need a bit more information:\n" + "\n".join(
            f"- {item.prompt}" for item in result.missing
        )
    return ToolAnswer(text=text, agent_used="orchestrator_need_input", needs_clarification=True)
