"""Orchestrator adapter for independent career-readiness planning."""

from __future__ import annotations

from app.domains.career_planning.interface import create_career_plan
from app.domains.profile.interface import get_profile
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.turn_context import ChatToolInput, TurnState


_NEEDS_ROLE_REPLY = (
    "To build a useful career-readiness plan, I need to know which role you're "
    "aiming for — e.g. quant researcher, compliance officer, fintech product "
    "manager, or risk analyst. What role are you targeting?"
)

def _has_known_target_role(state: TurnState) -> bool:
    if state.target_role_hint:
        return True
    profile = get_profile(state.user_id) if state.user_id else None
    return bool((profile or {}).get("target_role_raw") or (profile or {}).get("target_role_std"))


def _template_reply(result: dict) -> str:
    """Render the structured result without another generative step."""
    lines = [
        f"Target role: {result['target_role']}",
        "",
        "Current fit:",
        result["current_fit"],
    ]

    assessments = result.get("skill_assessment") or []
    if assessments:
        lines.extend(["", "Capability assessment:"])
        lines.extend(
            f"- {item['skill']} ({item['status']}): {item['evidence']}"
            for item in assessments
        )

    for phase in result.get("phases") or []:
        lines.extend(["", f"{phase['name']} — {phase['timeframe']}"])
        lines.extend(f"- {action}" for action in phase["actions"])
        lines.append("Success indicators:")
        lines.extend(f"- {indicator}" for indicator in phase["success_indicators"])

    if result.get("success_indicators"):
        lines.extend(["", "Overall success indicators:"])
        lines.extend(f"- {indicator}" for indicator in result["success_indicators"])
    if result.get("notes"):
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in result["notes"])
    return "\n".join(lines)


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    if not _has_known_target_role(state):
        return ToolAnswer(
            text=_NEEDS_ROLE_REPLY,
            agent_used="career_agent",
            needs_clarification=True,
        )

    result = create_career_plan(user_id=state.user_id, target_role=state.target_role_hint)
    # Deterministic rendering guarantees that a second LLM cannot add
    # academic recommendations after the domain has validated its result.
    return ToolAnswer(
        text=_template_reply(result),
        sources=list(result.get("sources") or []),
        agent_used="career_agent",
    )


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    """Fail honestly without switching to an academically-oriented answer path."""
    return ToolAnswer(
        text=(
            "I couldn't build a reliable personalised readiness plan right now. "
            "Please try again shortly; your target role and profile "
            "evidence will be used when the planning service is available."
        ),
        agent_used="career_agent_fallback",
    )


CAREER_TOOL = Tool(
    name="career",
    description="Evidence-based career-fit assessment and phased job-readiness planning.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"career"}),
)
