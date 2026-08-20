"""
Conversation service — block-based incremental history summarization built
on top of app/modules/chatbot/repository.py. Pairs an LLM call (summarize a
frozen block) with repository writes.

Block-freezing is split into two halves, on purpose, to close a concurrency
hole: multiple background freeze tasks for the same session used to each
independently decide "this block needs freezing" off a stale read, redoing
the work and racing on whose state update survived (see
app/modules/chatbot/schema/student_conversations_lock.sql for the fix's
schema half). Now:
  - should_freeze() is a cheap, synchronous, side-effect-free check — called
    from app/modules/chatbot/api.py right after a turn completes, *before*
    the response is sent, together with store.try_lock(session_id,
    "summarizing") to atomically claim the right to freeze.
  - freeze_and_unlock() does the slow part (one Kimi call to summarize) and
    is what actually runs as a FastAPI BackgroundTask, but only for the one
    caller that won the lock — so it never adds latency to the turn that
    triggers it, and never races with another freeze of the same session.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.clients.kimi_client import build_chat_llm
from app.core.config import settings
from app.modules.chatbot.models import ConversationState, HistoryBlock
from app.modules.chatbot.repository import ConversationStore

_SUMMARY_PROMPT = """\
Summarize the following portion of a conversation between a prospective \
student and an NUS MSc DFinTech admissions assistant, in 2-4 concise \
sentences. Focus on what topics were discussed and any preferences, facts, \
or context the user mentioned that could matter later in the conversation. \
Write the summary in English regardless of the conversation's language. Be \
factual — do not add commentary or advice of your own.

Respond with ONLY the summary text, no preamble."""


def summarize_block(messages: list[BaseMessage]) -> str:
    """One Kimi call, permanent once computed — a block is only ever
    summarized from its raw source, never from a previous summary, so
    repeated compression drift can't accumulate. Never raises (falls back to
    a generic placeholder so a transient failure doesn't crash the
    background task or silently drop the block)."""
    try:
        transcript = "\n".join(
            f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
            for m in messages
        )
        # max_tokens is generous relative to the desired 2-4 sentence
        # summary: Kimi is a reasoning model and spends part of the budget
        # on hidden reasoning_content before the visible answer (see
        # app/clients/kimi_client.py) — too tight a budget truncates to "".
        llm = build_chat_llm(temperature=0, max_tokens=1000)
        response = llm.invoke([
            SystemMessage(content=_SUMMARY_PROMPT),
            HumanMessage(content=transcript),
        ])
        return response.content.strip()
    except Exception as exc:
        print(f"[conversation_service] Warning: summarize_block failed — {exc}")
        return "(summary unavailable for this portion of the conversation)"


def render_summaries(blocks: list[HistoryBlock]) -> str:
    """Renders frozen block summaries into a compact text block for the LLM
    prompt. Empty list -> empty string (caller should skip injecting a
    SystemMessage entirely in that case)."""
    if not blocks:
        return ""
    lines = [f"- (turns {b.start_turn}-{b.end_turn}) {b.summary}" for b in blocks]
    return "Summary of earlier parts of this conversation:\n" + "\n".join(lines)


def should_freeze(state: ConversationState) -> bool:
    """Pure, side-effect-free check: would the *next* turn push the raw tail
    over settings.history_raw_tail_max? Called synchronously (see
    app/modules/chatbot/api.py) so the freeze lock can be claimed before the
    response is sent — freezing the oldest settings.history_block_size turns
    then happens in the background via freeze_and_unlock(), so the summary
    is already available by the time it's next needed."""
    next_tail_turns = (state.turn_count + 1) - state.last_frozen_end
    if next_tail_turns <= settings.history_raw_tail_max:
        return False
    n_msgs = 2 * settings.history_block_size  # strict Human/AI pairing assumed
    return len(state.raw_tail) >= n_msgs


def freeze_and_unlock(store: ConversationStore, session_id: str) -> None:
    """Background-task entry point (see app/modules/chatbot/api.py) — runs
    only for the one caller that already won the freeze lock via
    store.try_lock(session_id, "summarizing"). Does the slow part (one Kimi
    call to summarize), archives the block, and always releases the lock via
    store.unlock_after_freeze() — including on failure, so a crashed or
    errored attempt can't wedge the session past settings.freeze_lock_ttl_seconds.
    Never raises."""
    try:
        state = store.get_state(session_id)
    except Exception as exc:
        print(f"[conversation_service] Warning: freeze_and_unlock failed to read state — {exc}")
        return  # nothing safe to write back; the TTL will recover the lock

    try:
        block_size = settings.history_block_size
        n_msgs = 2 * block_size
        if len(state.raw_tail) >= n_msgs:
            block_messages = state.raw_tail[:n_msgs]
            start_turn = state.last_frozen_end + 1
            end_turn = state.last_frozen_end + block_size
            summary = summarize_block(block_messages)
            block = HistoryBlock(
                start_turn=start_turn, end_turn=end_turn, summary=summary,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            store.archive_block(session_id, block, block_messages)

            state.last_frozen_end = end_turn
            state.raw_tail = state.raw_tail[n_msgs:]
            state.history_summaries = state.history_summaries + [block]
    except Exception as exc:
        print(f"[conversation_service] Warning: freeze_and_unlock failed — {exc}")
    finally:
        try:
            store.unlock_after_freeze(session_id, state)
        except Exception as exc:
            print(f"[conversation_service] Warning: freeze_and_unlock failed to unlock — {exc}")
