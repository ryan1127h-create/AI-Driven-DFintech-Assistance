"""
Assessment tool — orchestrator adapter for the assessment specialist
domain (see app/domains/specialist/assessment/): extracts what the domain
needs from TurnState, calls assess(), wraps the result in a ToolAnswer.

The "is there enough to assess at all" check lives here, not in the
domain — needs_clarification is orchestrator vocabulary the domain
shouldn't need to know about (same pattern as career_planning_tool.py's
_has_known_target_role() check). It's also declared as this tool's
required_input (see orchestrator/dispatch/requirements.py) even though
it's unreachable via the normal dispatch path today —
classification.classify_intent() short-circuits to the "general" intent
on an empty message, so no tool is ever routed to at all in that case.
Declaring it anyway keeps this tool's contract honest rather than leaving
a requirement it silently doesn't enforce.
"""

from __future__ import annotations

from app.domains.specialist.assessment.interface import assess
from app.tools.contracts import MissingInputField, OnEvent, Tool, ToolAnswer
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages

_NEEDS_BACKGROUND_REPLY = (
    "Please share your academic background, work experience, and career "
    "goals so I can assess your application readiness."
)


def _required_input(state: TurnState) -> tuple[MissingInputField, ...]:
    if last_human_message(state.messages):
        return ()
    return (MissingInputField(slot="applicant_background", prompt=_NEEDS_BACKGROUND_REPLY),)


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    # Defense-in-depth only — see _required_input()'s docstring above.
    last_user_message = last_human_message(state.messages)
    if not last_user_message:
        return ToolAnswer(text=_NEEDS_BACKGROUND_REPLY, agent_used="assessment_agent", needs_clarification=True)

    chat_history = to_chat_messages(state.messages)
    text, sources = assess(last_user_message, chat_history, on_event=on_event)
    return ToolAnswer(text=text, sources=sources, agent_used="assessment_agent")


ASSESSMENT_TOOL = Tool(
    name="assessment",
    description="Structured, personalised Application Readiness Assessment from the applicant's shared background.",
    input_model=ChatToolInput,
    handler=_handler,
    trigger_intents=frozenset({"assessment"}),
    required_input=_required_input,
)
