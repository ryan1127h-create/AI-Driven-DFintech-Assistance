"""
Turn service — orchestrates one conversational turn: loads conversation
state + applicant profile, classifies intent, dispatches to the matched
tool(s), and records the updated state. This is the "engine" behind the
/chat endpoint (see api.py), kept independent of FastAPI so it stays easy
to test or reuse from another entry point.

Conversation state (storage, locking, summarization, listing/history/
rollback) lives entirely in app.domains.conversation — this module only
ever reaches it through conversation.interface, never its repository/
service internals directly, per the module-isolation rule: cross-domain
data only flows through a domain's public interface. Same rule for profile
data, read-only here through profile.interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.domains.conversation import interface as conversation
from app.domains.profile.interface import get_profile_summary_text
from app.orchestrator import classification, dispatch
from app.tools.turn_context import OnEvent, TurnState


@dataclass
class ChatTurnResult:
    session_id: str
    reply: str
    agent_used: str
    user_message: str
    intents: list[str] = field(default_factory=list)


def run_turn(
    session_id: str | None, message: str, user_id: str,
    on_event: OnEvent | None = None,
) -> ChatTurnResult:
    """
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries. This is never a full-history read: the row itself stays
      small regardless of how long the conversation has run. Ownership is
      checked/claimed by conversation.get_state() — an existing session
      owned by someone else raises ForbiddenError before any LLM/DB work
      happens.
    - Reads the applicant's profile (read-only) for the profile-summary
      system message (this already includes lifecycle stage when known).
    - Prepends the profile summary and the history-block summaries, then
      the raw tail, then the new message.
    - Classifies intent, then dispatches to the matched tool(s).
    - Records the turn (raw tail grows by one turn).

    The caller (see api.py) is responsible for scheduling the post-turn
    background task (block-freezing) — that needs FastAPI's
    BackgroundTasks, which this function deliberately knows nothing about.

    `on_event`, when given, is forwarded into classification/dispatch to
    report progress ("step") and answer-text ("token") events for the
    streaming endpoint. Every tool treats a missing/None value as "emit
    nothing", so leaving this at its default here (the plain /chat
    endpoint) changes nothing about this function's behavior or return
    value.
    """
    session_id = session_id or conversation.new_session_id()
    state = conversation.get_state(session_id, user_id)

    new_message = HumanMessage(content=message)

    profile_text = get_profile_summary_text(user_id)
    summaries_text = conversation.render_summaries(state.history_summaries)

    system_blocks = []
    if profile_text:
        system_blocks.append(SystemMessage(content=profile_text))
    if summaries_text:
        system_blocks.append(SystemMessage(content=summaries_text))

    llm_messages = system_blocks + state.raw_tail + [new_message]

    intents, target_role_hint, program_hints, reply_language = classification.classify_intent(
        llm_messages, on_event
    )
    turn_state = TurnState(
        messages=llm_messages, user_id=user_id,
        target_role_hint=target_role_hint, program_hints=program_hints,
        reply_language=reply_language,
    )
    ai_message, reply, agent_used = dispatch.answer_turn(turn_state, intents, on_event)

    conversation.record_turn(session_id, state, new_message, ai_message, intents, agent_used)

    return ChatTurnResult(
        session_id=session_id, reply=reply, agent_used=agent_used,
        user_message=message, intents=intents,
    )
