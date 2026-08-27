import json
import queue
import threading
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.modules.auth.interface import get_current_user_id
from app.modules.chatbot import conversation_service, service
from app.modules.chatbot.repository import get_session_store
from app.modules.chatbot.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    RollbackRequest,
    RollbackResponse,
)

router = APIRouter()


# Deliberately a sync `def` (not `async def`): service.run_turn() does
# blocking LLM calls and psycopg queries, and FastAPI runs sync path
# operations in a threadpool so the event loop stays free for other
# requests — same reasoning as course_recommendation/program_comparison/
# career_planning's api.py. An `async def` here would block the entire
# worker's event loop for the duration of every chat turn.
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """
    Main conversational endpoint. Delegates the actual turn (state load,
    prompt assembly, supervisor graph invocation, state save) to
    app/modules/chatbot/service.py.

    An existing session can be rejected up front by two distinct locks
    (see store.try_lock() in app/modules/chatbot/repository.py), reported
    with different HTTP status codes so the frontend can tell them apart:
      - 409 Conflict — this session's *previous* /chat call is still being
        processed. Guards the whole run_turn() read-modify-write: without
        this, two genuinely concurrent turns for the same session could
        each read the same starting state and one would silently overwrite
        the other's saved turn (lost update).
      - 423 Locked — a prior turn's history-block freeze is still running
        in the background — see app/modules/chatbot/conversation_service.py
        for why that lock has to be claimed synchronously, before any
        response is sent, rather than inside the background task itself.

    A session belonging to a different authenticated user is rejected with
    403 (raised by service.run_turn() as a PermissionError — see its
    docstring) before any reply is generated.

    A brand-new session (no session_id in the request) never needs locking:
    service.run_turn() mints a fresh random UUID, so no concurrent request
    could already be targeting it.

    The profile is read-only here — there is no profile-update background
    task any more (see app/modules/profile/ for how profiles get created).
    """
    session_id = str(request.session_id) if request.session_id is not None else None
    store = get_session_store()
    is_existing_session = session_id is not None

    if is_existing_session:
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

    try:
        result = service.run_turn(session_id, request.message, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        # Full detail stays server-side; clients get a generic message so
        # DB/provider errors never leak into responses (same pattern as
        # course_recommendation/program_comparison/career_planning's api.py).
        print(f"[chatbot.api] Error: chat turn failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to process the chat message.") from exc
    finally:
        # Always release the processing lock we took above, success or
        # failure, so a crashed turn can't wedge the session past the
        # freeze_lock_ttl_seconds staleness window.
        if is_existing_session:
            store.release_lock(session_id)

    # Claim the freeze lock (separately, after the processing lock above
    # has already been released) if this turn pushed the raw tail over the
    # limit — only the winner schedules the actual (slow) summarization as
    # a background task, so a second concurrent/rapid-fire turn can never
    # redundantly re-freeze the same block (see conversation_service.py).
    state = store.get_state(result.session_id)
    if conversation_service.should_freeze(state) and store.try_lock(result.session_id, "summarizing", user_id) is None:
        background_tasks.add_task(conversation_service.freeze_and_unlock, store, result.session_id)

    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        agent_used=result.agent_used,
    )


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Streaming counterpart of POST /chat — same locking/ownership/freeze
# semantics, but the turn runs on a background thread that reports progress
# ("step") and answer-text ("token") events through service.run_turn()'s
# on_event callback (see agents/state.py::AgentState.on_event), which this
# generator relays to the client as Server-Sent Events as they arrive,
# instead of waiting for the whole turn to finish before responding.
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

    def event_stream():
        q: "queue.Queue[dict | None]" = queue.Queue()
        outcome: dict = {}

        def worker():
            try:
                outcome["result"] = service.run_turn(session_id, request.message, user_id, on_event=q.put)
            except Exception as exc:  # noqa: BLE001 — reported to the client as an `error` event below
                outcome["error"] = exc
            finally:
                q.put(None)  # sentinel — always enqueued, success or failure

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        # `lock_released` tracks whether the block below has already done it,
        # so the `finally` doesn't call it a second time on the normal path.
        #
        # try/finally so the processing lock is always released even if the
        # client disconnects mid-stream (Starlette raises GeneratorExit into
        # this generator at the current yield in that case).
        lock_released = False
        try:
            while (item := q.get()) is not None:
                yield _sse(item["type"], item)
            thread.join()

            # Release the processing lock now, right after run_turn()
            # finishes — same point POST /chat releases it (see that
            # endpoint above) — and BEFORE the freeze-scheduling block
            # below. That block's store.try_lock(..., "summarizing", ...)
            # is a CAS that only succeeds when this session's status is
            # 'normal' (or stale); releasing late (the previous behavior:
            # only in `finally`, after the "done" event) meant this
            # request's own still-held "processing" status made that CAS
            # fail every single time, so should_freeze()-triggered blocks
            # were never actually scheduled via this endpoint — the raw
            # tail grew unboundedly instead of ever being archived.
            if is_existing_session:
                store.release_lock(session_id)
                lock_released = True

            if "error" in outcome:
                exc = outcome["error"]
                if isinstance(exc, PermissionError):
                    yield _sse("error", {"detail": str(exc)})
                else:
                    print(f"[chatbot.api] Error: chat turn failed (stream) — {exc!r}")
                    yield _sse("error", {"detail": "Failed to process the chat message."})
                return

            result = outcome["result"]

            # Same freeze-scheduling logic as POST /chat above.
            state = store.get_state(result.session_id)
            if conversation_service.should_freeze(state) and \
                    store.try_lock(result.session_id, "summarizing", user_id) is None:
                background_tasks.add_task(conversation_service.freeze_and_unlock, store, result.session_id)

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
# supabase_cached/supabase backends, same reasoning as chat() above.
@router.delete("/chat/{session_id}")
def clear_session(session_id: UUID, user_id: str = Depends(get_current_user_id)):
    """Clear a specific session's conversation history (and its archived
    messages, via student.messages' ON DELETE CASCADE foreign key). A
    session belonging to a different authenticated user is rejected with
    403; a session that doesn't exist is a no-op (kept idempotent, same as
    before auth existed) rather than an error."""
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
    return ConversationListResponse(conversations=service.list_conversations(user_id))


@router.get("/chat/{session_id}/history", response_model=ConversationHistoryResponse)
def get_history(session_id: UUID, user_id: str = Depends(get_current_user_id)):
    """Full turn-by-turn transcript for one conversation — archived turns
    (real original text, not just their summary) followed by the still-live
    raw tail. A session belonging to a different authenticated user is
    rejected with 403; a session_id nothing was ever saved under is 404."""
    try:
        return service.get_conversation_history(str(session_id), user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        print(f"[chatbot.api] Error: get_history failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to load conversation history.") from exc


# Sync `def` — rollback_conversation() does blocking psycopg calls under the
# supabase_cached/cached backends, same reasoning as chat()/clear_session() above.
@router.post("/chat/{session_id}/rollback", response_model=RollbackResponse)
def rollback(session_id: UUID, request: RollbackRequest, user_id: str = Depends(get_current_user_id)):
    """
    Deletes the most recent `turns` turns from this conversation — only
    ever the still-unarchived tail (see service.py::rollback_conversation
    and the module's underlying table docs for why archived turns can never
    be rolled back). This is a read-modify-write over the exact same
    conversation state a /chat turn mutates, so it takes the same
    "processing" lock POST /chat does, with the same 409/423 split — see
    that endpoint's docstring for why.
    """
    session_id_str = str(session_id)
    store = get_session_store()

    blocking_status = store.try_lock(session_id_str, "processing", user_id)
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

    try:
        state = service.rollback_conversation(session_id_str, request.turns, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        print(f"[chatbot.api] Error: rollback failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Failed to roll back the conversation.") from exc
    finally:
        store.release_lock(session_id_str)

    return RollbackResponse(
        session_id=session_id_str,
        turn_count=state.turn_count,
        archived_turn_count=state.last_frozen_end,
        removed_turns=request.turns,
    )
