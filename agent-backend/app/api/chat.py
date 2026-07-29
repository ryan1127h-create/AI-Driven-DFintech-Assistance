import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.supervisor import supervisor_graph
from app.core.config import settings
from app.core.redis_client import ping as redis_ping
from app.core.session_store import get_session_store, maybe_freeze_block, render_summaries
from app.core.user_profile_store import (
    get_user_profile_store,
    summarize_profile,
    update_profile_after_turn,
)

router = APIRouter()

# Backend is selected by SESSION_STORE_BACKEND ("memory", "redis", or
# "supabase_cached"); see app/core/session_store.py for details.
_store = get_session_store()
_profile_store = get_user_profile_store()

# No login/auth exists yet — every session shares one placeholder profile
# until real user identity is wired in (see plan Phase 5). Swapping this for
# a real per-request user id later is a one-line change here; the storage
# layer (app/core/user_profile_store.py) doesn't need to change.
DEFAULT_USER_ID = "user001"


# ── Request / Response schemas ─────────────────────────────────────────────────
class UserProfile(BaseModel):
    stage: str = "prospect"   # prospect | applicant | admitted | student | alumni
    name: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    user_profile: Optional[UserProfile] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    agent_used: str


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main conversational endpoint.
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries (see app/core/session_store.py — Phase 6). Unlike Phase 5,
      this is never a full-history read: the row itself stays small
      regardless of how long the conversation has run.
    - Prepends the applicant profile summary and the history-block
      summaries, then the raw tail, then the new message.
    - Runs the LangGraph supervisor.
    - Persists the updated state (raw tail grows by one turn).
    - Schedules two background tasks: profile extraction, and a check for
      whether the next turn would overflow the raw tail (if so, the oldest
      block gets frozen into a summary now, ready before it's needed).
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        state = _store.get_state(session_id)
        user_stage = request.user_profile.stage if request.user_profile else "prospect"

        new_message = HumanMessage(content=request.message)

        profile = _profile_store.get(DEFAULT_USER_ID)
        profile_text = summarize_profile(profile)
        summaries_text = render_summaries(state.history_summaries)

        system_blocks = []
        if profile_text:
            system_blocks.append(SystemMessage(content=profile_text))
        if summaries_text:
            system_blocks.append(SystemMessage(content=summaries_text))

        llm_messages = system_blocks + state.raw_tail + [new_message]

        # Run the supervisor graph
        result = supervisor_graph.invoke({
            "messages": llm_messages,
            "user_stage": user_stage,
            "agent_used": "",
            "reply": "",
        })

        # result["messages"] is llm_messages plus whatever the graph
        # appended (exactly one AI message) — slice by position rather than
        # equality, since two messages could coincidentally match content.
        new_ai_messages = result["messages"][len(llm_messages):]

        state.turn_count += 1
        state.raw_tail = state.raw_tail + [new_message] + new_ai_messages
        _store.save_state(session_id, state)

        background_tasks.add_task(maybe_freeze_block, _store, session_id)
        background_tasks.add_task(
            update_profile_after_turn,
            DEFAULT_USER_ID, request.message, result["reply"], result.get("intents", []),
        )

        return ChatResponse(
            session_id=session_id,
            reply=result["reply"],
            agent_used=result["agent_used"],
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session's conversation history (and its archived
    blocks, via the conversation_archive foreign key's ON DELETE CASCADE)."""
    _store.delete(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/health")
async def health():
    """Liveness check, including session store backend status."""
    backend = settings.session_store_backend
    status = {"status": "ok", "phase": 2, "session_store": backend}
    if backend == "redis":
        status["redis_connected"] = redis_ping()
    return status
