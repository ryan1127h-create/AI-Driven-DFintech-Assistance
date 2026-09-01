import json
import queue
import threading
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.errors import ForbiddenError
from app.domains.auth.interface import get_current_user_id
from app.orchestrator import conversation_service, turn_service
from app.orchestrator.conversation_repository import get_session_store
from app.orchestrator.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    RollbackRequest,
    RollbackResponse,
)

router = APIRouter()


def _try_lock_or_raise(store, session_id: str, user_id: str) -> None:
    """Shared lock-acquisition for every endpoint that mutates conversation
    state (chat, chat/stream, rollback) — two distinct locks, reported with
    different HTTP status codes so the frontend can tell them apart:
      - 409 Conflict — this session's *previous* turn/rollback is still
        being processed. Guards the whole read-modify-write: without this,
        two genuinely concurrent turns for the same session could each
        read the same starting state and one would silently overwrite the
        other's saved turn (lost update).
      - 423 Locked — a prior turn's history-block freeze is still running
        in the background (see conversation_service.py for why that lock
        has to be claimed synchronously, before any response is sent,
        rather than inside the background task itself)."""
    blocking_status = store.try_lock(session_id, "processing", user_id)
    if blocking_status == "summarizing":
        raise HTTPException(
            status_code=423,
            detail="This conversation is being summarized, please retry shortly.",
            headers={"Retry-After": "5"},
        )
    if blocking_status is not None:
        raise HTTPException(
            status_code=409,
            detail="This conversation is already processing another message, please retry shortly.",
            headers={"Retry-After": "3"},
        )


def _schedule_freeze_if_needed(store, background_tasks: BackgroundTasks, session_id: str, user_id: str) -> None:
    """Claims the freeze lock (separately, after the processing lock above
    has already been released) if this turn pushed the raw tail over the
    limit — only the winner schedules the actual (slow) summarization as a
    background task, so a second concurrent/rapid-fire turn can never
    redundantly re-freeze the same block."""
    state = get_session_store().get_state(session_id)
    if conversation_service.should_freeze(state) and store.try_lock(session_id, "summarizing", user_id) is None:
        background_tasks.add_task(conversation_service.freeze_and_unlock, store, session_id)


# Deliberately a sync `def` (not `async def`): turn_service.run_turn() does
# blocking LLM calls and psycopg queries, and FastAPI runs sync path
# operations in a threadpool so the event loop stays free for other
# requests.
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """
    Main conversational endpoint. Delegates the actual turn (state load,
    prompt assembly, intent classification + dispatch, state save) to
    turn_service.py.

    A brand-new session (no session_id in the request) never needs locking:
    turn_service.run_turn() mints a fresh random UUID, so no concurrent
    request could already be targeting it. A session belonging to a
    different authenticated user is rejected with 403 (raised by
    turn_service.run_turn() as ForbiddenError) before any reply is
    generated.
    """
    session_id = str(request.session_id) if request.session_id is not None else None
    store = get_session_store()
    is_existing_session = session_id is not None

    if is_existing_session:
        _try_lock_or_raise(store, session_id, user_id)

    try:
        result = turn_service.run_turn(session_id, request.message, user_id)
    finally:
        # Always release the processing lock we took above, success or
        # failure, so a crashed turn can't wedge the session past the
        # freeze_lock_ttl_seconds staleness window.
        if is_existing_session:
            store.release_lock(session_id)

    _schedule_freeze_if_needed(store, background_tasks, result.session_id, user_id)

    return ChatResponse(session_id=result.session_id, reply=result.reply, agent_used=result.agent_used)


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Streaming counterpart of POST /chat — same locking/ownership/freeze
# semantics, but the turn runs on a background thread that reports progress
# ("step") and answer-text ("token") events through turn_service.run_turn()'s
# on_event callback, which this generator relays to the client as
# Server-Sent Events as they arrive, instead of waiting for the whole turn
# to finish before responding.
@router.post("/chat/stream")
def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """
    Same request shape as POST /chat. Response is `text/event-stream`:
      event: step   — {"type":"step","stage":..., ...}      (progress/path)
      event: token  — {"type":"token","text":"..."}          (answer text, in order)
      event: done   — {"session_id":..., "reply":..., "agent_used":...}
      event: error  — {"detail":"..."}                       (mid-turn failure)

    The 409/423 lock checks happen up front, before the stream opens, exactly
    like POST /chat — they're fast and synchronous, so there's no reason to
    make the client parse them out of an SSE frame instead of a normal HTTP
    status. Only failures that happen during the turn itself (LLM/DB errors)
    become an `error` event, since by then the response has already started.
    """
    session_id = str(request.session_id) if request.session_id is not None else None
    store = get_session_store()
    is_existing_session = session_id is not None

    if is_existing_session:
        _try_lock_or_raise(store, session_id, user_id)

    def event_stream():
        q: "queue.Queue[dict | None]" = queue.Queue()
        outcome: dict = {}

        def worker():
            try:
                outcome["result"] = turn_service.run_turn(session_id, request.message, user_id, on_event=q.put)
            except Exception as exc:  # noqa: BLE001 — reported to the client as an `error` event below
                outcome["error"] = exc
            finally:
                q.put(None)  # sentinel — always enqueued, success or failure

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        # `lock_released` tracks whether the block below has already done
        # it, so the `finally` doesn't call it a second time on the normal
        # path. try/finally so the processing lock is always released even
        # if the client disconnects mid-stream (Starlette raises
        # GeneratorExit into this generator at the current yield in that
        # case).
        lock_released = False
        try:
            while (item := q.get()) is not None:
                yield _sse(item["type"], item)
            thread.join()

            # Release the processing lock now, right after run_turn()
            # finishes, and BEFORE the freeze-scheduling block below —
            # that block's store.try_lock(..., "summarizing", ...) is a CAS
            # that only succeeds when this session's status is 'normal' (or
            # stale); releasing late (only in a bare `finally`, after the
            # "done" event) would mean this request's own still-held
            # "processing" status makes that CAS fail every time, so
            # should_freeze()-triggered blocks would never actually get
            # scheduled via this endpoint — the raw tail would grow
            # unboundedly instead of ever being archived.
            if is_existing_session:
                store.release_lock(session_id)
                lock_released = True

            if "error" in outcome:
                exc = outcome["error"]
                if isinstance(exc, ForbiddenError):
                    yield _sse("error", {"detail": str(exc)})
                else:
                    print(f"[orchestrator.api] Error: chat turn failed (stream) — {exc!r}")
                    yield _sse("error", {"detail": "Failed to process the chat message."})
                return

            result = outcome["result"]
            _schedule_freeze_if_needed(store, background_tasks, result.session_id, user_id)

            yield _sse("done", {
                "session_id": result.session_id,
                "reply": result.reply,
                "agent_used": result.agent_used,
            })
        finally:
            if is_existing_session and not lock_released:
                store.release_lock(session_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream", background=background_tasks)


# Also a sync `def` — store.delete() is a blocking psycopg call under the
# supabase_cached backend, same reasoning as chat() above.
@router.delete("/chat/{session_id}")
def clear_session(session_id: UUID, user_id: str = Depends(get_current_user_id)):
    """Clear a specific session's conversation history (and its archived
    messages, via the archive table's ON DELETE CASCADE foreign key). A
    session belonging to a different authenticated user is rejected with
    403; a session that doesn't exist is a no-op (kept idempotent) rather
    than an error."""
    store = get_session_store()
    state = store.get_state(str(session_id))
    if state.user_id is not None and state.user_id != user_id:
        raise HTTPException(status_code=403, detail="This conversation belongs to a different user.")
    store.delete(str(session_id))
    return {"status": "cleared", "session_id": str(session_id)}


@router.get("/chat/sessions", response_model=ConversationListResponse)
def list_sessions(user_id: str = Depends(get_current_user_id)):
    """All of the current user's conversations, most recently active first —
    for a frontend sidebar. Backends with no per-user index (the "redis"
    session_store_backend) return an empty list rather than erroring."""
    return ConversationListResponse(conversations=turn_service.list_conversations(user_id))


@router.get("/chat/{session_id}/history", response_model=ConversationHistoryResponse)
def get_history(session_id: UUID, user_id: str = Depends(get_current_user_id)):
    """Full turn-by-turn transcript for one conversation — archived turns
    (real original text, not just their summary) followed by the still-live
    raw tail. A session belonging to a different authenticated user is
    rejected with 403; a session_id nothing was ever saved under is 404."""
    return turn_service.get_conversation_history(str(session_id), user_id)


# Sync `def` — rollback_conversation() does blocking psycopg calls under the
# supabase_cached backend, same reasoning as chat()/clear_session() above.
@router.post("/chat/{session_id}/rollback", response_model=RollbackResponse)
def rollback(session_id: UUID, request: RollbackRequest, user_id: str = Depends(get_current_user_id)):
    """
    Deletes the most recent `turns` turns from this conversation — only
    ever the still-unarchived tail (see turn_service.py::rollback_conversation
    for why archived turns can never be rolled back). This is a
    read-modify-write over the exact same conversation state a /chat turn
    mutates, so it takes the same "processing" lock POST /chat does, with
    the same 409/423 split.
    """
    session_id_str = str(session_id)
    store = get_session_store()

    _try_lock_or_raise(store, session_id_str, user_id)

    try:
        state = turn_service.rollback_conversation(session_id_str, request.turns, user_id)
    finally:
        store.release_lock(session_id_str)

    return RollbackResponse(
        session_id=session_id_str,
        turn_count=state.turn_count,
        archived_turn_count=state.last_frozen_end,
        removed_turns=request.turns,
    )
