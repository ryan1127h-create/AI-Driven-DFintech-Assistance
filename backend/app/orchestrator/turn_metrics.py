"""
Reads a turn's agent_used string into what the staff dashboard counts: the
agents that took part, the ones among them that failed, and the turn's
overall outcome.

agent_used is "+"-joined: one part per agent that answered (a mixed
question has several), each "<tool>_agent" with an optional suffix —
_fallback (the tool fell back to a canned reply), _error / _timeout /
_unavailable (dispatch gave up on it) — plus the markers "revised" (the
evaluator had the answer redone) and "clarify" (it replaced the answer with
a question). The orchestrator's own replies are "orchestrator_need_input",
"orchestrator_decline" and "orchestrator_error"; "supervisor" is the
general-chat answer; "orchestrator_redirect" is the stage policy's fixed
reply (app/core/stage_policy.py) when no tool applies at the user's stage.
"""

from __future__ import annotations

from dataclasses import dataclass

_FAILURE_SUFFIXES = ("_fallback", "_error", "_timeout", "_unavailable")
_ORCHESTRATOR_OUTCOMES = {
    "orchestrator_need_input": "need_input",
    "orchestrator_decline": "declined",
    # A complete answer (the outcome column only takes the values below).
    "orchestrator_redirect": "answered",
    "orchestrator_error": "error",
}
# Worst first: the turn's outcome is the worst thing that happened in it.
_OUTCOME_ORDER = ("error", "declined", "need_input", "fallback", "revised", "answered")


@dataclass(frozen=True)
class TurnOutcome:
    agents: list[str]
    failed_agents: list[str]
    outcome: str


def _agent_name(part: str) -> tuple[str, str | None]:
    """("course_recommendation_agent_fallback") -> ("course_recommendation", "_fallback")."""
    suffix = next((s for s in _FAILURE_SUFFIXES if part.endswith(s)), None)
    name = part[: -len(suffix)] if suffix else part
    return name.removesuffix("_agent"), suffix


def read_agent_used(agent_used: str) -> TurnOutcome:
    agents: list[str] = []
    failed: list[str] = []
    outcomes: set[str] = set()
    for part in filter(None, (agent_used or "").split("+")):
        if part == "revised":
            outcomes.add("revised")
        elif part == "clarify":
            outcomes.add("need_input")
        elif part in _ORCHESTRATOR_OUTCOMES:
            outcomes.add(_ORCHESTRATOR_OUTCOMES[part])
            agents.append("orchestrator")
            if part == "orchestrator_error":
                failed.append("orchestrator")
        else:
            name, suffix = _agent_name(part)
            agents.append(name)
            if suffix:
                failed.append(name)
                outcomes.add("fallback" if suffix == "_fallback" else "error")
    outcome = next((o for o in _OUTCOME_ORDER if o in outcomes), "answered")
    return TurnOutcome(agents=sorted(set(agents)), failed_agents=sorted(set(failed)), outcome=outcome)
