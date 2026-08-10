from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.modules.chatbot import conversation_service, service
from app.modules.chatbot.repository import get_session_store
from app.modules.chatbot.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main conversational endpoint. Delegates the actual turn (state load,
    prompt assembly, supervisor graph invocation, state save) to
    app/modules/chatbot/service.py.

    If this session is currently being summarized (a prior turn's freeze is
    still in progress), the request is rejected up front with 423 Locked
    rather than being processed — see
    app/modules/chatbot/conversation_service.py for why the freeze lock has
    to be claimed synchronously, before any response is sent, rather than
    inside the background task itself.

    The profile is read-only here — there is no profile-update background
    task any more (see app/modules/profile/ for how profiles get created).
    """
    session_id = str(request.session_id) if request.session_id is not None else None
    store = get_session_store()

    if session_id and store.is_locked(session_id):
        raise HTTPException(
            status_code=423,
            detail="This conversation is being summarized, please retry shortly.",
            headers={"Retry-After": "5"},
        )

    try:
        result = service.run_turn(session_id, request.message)

        # Claim the freeze lock synchronously (before the response is sent)
        # if this turn pushed the raw tail over the limit — only the winner
        # schedules the actual (slow) summarization as a background task, so
        # a second concurrent/rapid-fire turn can never redundantly re-freeze
        # the same block (see conversation_service.py).
        state = store.get_state(result.session_id)
        if conversation_service.should_freeze(state) and store.try_lock_for_freeze(result.session_id):
            background_tasks.add_task(conversation_service.freeze_and_unlock, store, result.session_id)

        return ChatResponse(
            session_id=result.session_id,
            reply=result.reply,
            agent_used=result.agent_used,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/chat/{session_id}")
async def clear_session(session_id: UUID):
    """Clear a specific session's conversation history (and its archived
    messages, via student.messages' ON DELETE CASCADE foreign key)."""
    get_session_store().delete(str(session_id))
    return {"status": "cleared", "session_id": str(session_id)}
