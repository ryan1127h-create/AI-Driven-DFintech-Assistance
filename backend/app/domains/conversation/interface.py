"""
Public interface of the conversation domain — the only module the
orchestrator (and any other domain, though none currently need to) is
allowed to import from app.domains.conversation. Everything else in this
package (repository, service internals) is private.

Current consumers:
    - orchestrator/turn_service.py uses get_state/record_turn/new_session_id
      for the per-turn read-modify-write, and render_summaries to build the
      prompt's history context.
    - orchestrator/api.py uses try_lock/release_lock/should_freeze/
      freeze_and_unlock for the request-level locking + background freeze
      scheduling, and delete_conversation/list_conversations/
      get_conversation_history/rollback_conversation directly for the
      corresponding /chat/* endpoints (these don't need a turn to run).

Usage:
    from app.domains.conversation import interface as conversation
    state = conversation.get_state(session_id, user_id)
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import AIMessage, HumanMessage

from app.domains.conversation import service
from app.domains.conversation.models import ConversationState, HistoryBlock

__all__ = [
    "ConversationState",
    "HistoryBlock",
    "new_session_id",
    "get_state",
    "record_turn",
    "record_turn_metrics",
    "open_case",
    "escalation_offer",
    "recent_transcript",
    "list_cases",
    "last_turn",
    "delete_conversation",
    "try_lock",
    "release_lock",
    "should_freeze",
    "freeze_and_unlock",
    "render_summaries",
    "for_prompt",
    "list_conversations",
    "get_conversation_history",
    "rollback_conversation",
]


def new_session_id() -> str:
    """A fresh session id for a brand-new conversation."""
    return service.new_session_id()


def get_state(session_id: str, user_id: str) -> ConversationState:
    """Loads a session's state, claiming it for `user_id` on first use.
    Raises ForbiddenError if it's already owned by someone else."""
    return service.get_state(session_id, user_id)


def record_turn(
    session_id: str, state: ConversationState,
    human_message: HumanMessage, ai_message: AIMessage,
    intents: list[str], agent_used: str, escalation_offer: dict | None = None,
) -> None:
    """Persists one completed turn: appends to the raw tail, bumps
    turn_count, logs the intent-classification result (and the offer to
    escalate it, when the turn made one)."""
    service.record_turn(session_id, state, human_message, ai_message, intents, agent_used, escalation_offer)


def open_case(case: dict, summarize: Callable[[], str]) -> dict | None:
    """Opens an escalation case for a conversation, or returns its open
    case of the same category; see service.open_case."""
    return service.open_case(case, summarize)


def escalation_offer(state: ConversationState) -> dict | None:
    """The offer to escalate that the latest turn made, or None."""
    return service.escalation_offer(state)


def recent_transcript(state: ConversationState, messages: int = 6) -> list[tuple[str, str]]:
    """[(role, text)] for the conversation's last few messages."""
    return service.recent_transcript(state, messages)


def list_cases(user_id: str) -> list[dict]:
    """The user's own escalation cases, newest first (no staff notes)."""
    return service.list_cases(user_id)


def record_turn_metrics(build: Callable[[], dict]) -> None:
    """Stores a turn's dashboard metrics, built by `build` only when they
    will be stored; best effort, never raises."""
    service.record_turn_metrics(build)


def last_turn(state: ConversationState) -> dict | None:
    """The last completed turn — {"user_message", "reply", "intents",
    "agent_used", "contexts"} — or None on a new conversation."""
    return service.last_turn(state)


def delete_conversation(session_id: str, user_id: str) -> None:
    """Deletes a session and its archive. Raises ForbiddenError if owned by
    someone else; a no-op for a session_id nothing was ever saved under."""
    service.delete_conversation(session_id, user_id)


def try_lock(session_id: str, status: str, user_id: str) -> str | None:
    """Atomically claims the session's "processing"/"summarizing" lock.
    Returns None on success, or the status string currently blocking it."""
    return service.try_lock(session_id, status, user_id)


def release_lock(session_id: str) -> None:
    service.release_lock(session_id)


def should_freeze(state: ConversationState) -> bool:
    """Whether the next turn would push the raw tail past the configured
    limit — call before scheduling freeze_and_unlock()."""
    return service.should_freeze(state)


def freeze_and_unlock(session_id: str) -> None:
    """Summarizes and archives the oldest history block, then releases the
    "summarizing" lock. Meant to run as a background task, after try_lock()
    has already claimed it — never raises."""
    service.freeze_and_unlock(session_id)


def render_summaries(history_summaries: list[HistoryBlock]) -> str:
    """Renders frozen block summaries into the compact text block a turn's
    prompt injects as history context. Empty list -> empty string."""
    return service.render_summaries(history_summaries)


def for_prompt(messages: list) -> list:
    """The raw tail as a prompt should see it: earlier assistant replies
    shortened to settings.history_reply_max_chars (start and end kept)."""
    return service.for_prompt(messages)


def list_conversations(user_id: str) -> list[dict]:
    """All of `user_id`'s conversations, most recently active first."""
    return service.list_conversations(user_id)


def get_conversation_history(session_id: str, user_id: str) -> dict:
    """Full turn-by-turn transcript: archived blocks followed by the live
    raw tail. Raises NotFoundError/ForbiddenError."""
    return service.get_conversation_history(session_id, user_id)


def rollback_conversation(session_id: str, turns: int, user_id: str) -> ConversationState:
    """Deletes the most recent `turns` not-yet-archived turns. Raises
    NotFoundError/ForbiddenError/ValidationError."""
    return service.rollback_conversation(session_id, turns, user_id)
