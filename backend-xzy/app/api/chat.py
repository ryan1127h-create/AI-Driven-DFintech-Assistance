import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.agents.supervisor import supervisor_graph

router = APIRouter()

# ── In-memory session store (Phase 1) ─────────────────────────────────────────
# Key   : session_id (str)
# Value : list of LangChain BaseMessage objects (full conversation history)
# NOTE  : This resets when the server restarts.
#         Will be replaced by Redis in Phase 2.
_sessions: dict = {}


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
    intent: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint.
    - Creates a new session_id if one is not provided.
    - Loads conversation history from the in-memory store.
    - Runs the LangGraph supervisor.
    - Persists the updated history back to the store.
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        history = _sessions.get(session_id, [])
        user_stage = request.user_profile.stage if request.user_profile else "prospect"

        # Append the new user message to history
        all_messages = history + [HumanMessage(content=request.message)]

        # Run the supervisor graph
        result = supervisor_graph.invoke({
            "messages": all_messages,
            "user_stage": user_stage,
            "agent_used": "",
            "reply": "",
        })

        # Persist updated history (includes the new AI reply via operator.add)
        _sessions[session_id] = result["messages"]

        return ChatResponse(
            session_id=session_id,
            reply=result["reply"],
            agent_used=result["agent_used"],
            intent=result.get("intent"),
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session's conversation history."""
    _sessions.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


@router.get("/health")
async def health():
    """Liveness check."""
    return {"status": "ok", "phase": 1}
