import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from langchain_core.messages import HumanMessage

from app.agents.supervisor import supervisor_graph
from common.profile import LifecycleStage

router = APIRouter()

# ── In-memory session store (Phase 1) ─────────────────────────────────────────
# Key   : session_id (str)
# Value : list of LangChain BaseMessage objects (full conversation history)
# NOTE  : This resets when the server restarts.
#         Will be replaced by Redis in Phase 2.
_sessions: dict = {}


# ── Wire vocabulary ────────────────────────────────────────────────────────────
# The frontend's own stage words, mapped onto the authority vocabulary defined in
# common/profile.py. Both of these mean "currently enrolled".
_WIRE_STAGE_ALIASES = {
    "student": LifecycleStage.current,
    "enrolled": LifecycleStage.current,
}
DEFAULT_WIRE_STAGE = LifecycleStage.prospect


def resolve_wire_stage(raw: object) -> LifecycleStage:
    """Map one wire stage word onto LifecycleStage, or raise naming the value.

    Deliberately no fallback: coercing an unrecognised stage to a default would
    advise, say, an alumnus as if they were a current student.
    """
    value = raw.strip().lower() if isinstance(raw, str) else raw
    # Alias keys are all strings, so only a string can match. Testing membership
    # with a non-string first would raise TypeError on an unhashable wire value
    # (a JSON list or object), turning a bad request into a 500.
    if isinstance(value, str) and value in _WIRE_STAGE_ALIASES:
        return _WIRE_STAGE_ALIASES[value]
    try:
        return LifecycleStage(value)
    except ValueError:
        accepted = sorted([s.value for s in LifecycleStage] + list(_WIRE_STAGE_ALIASES))
        raise ValueError(
            f"unsupported stage {raw!r}; accepted values: {', '.join(accepted)}"
        ) from None


# ── Request / Response schemas ─────────────────────────────────────────────────
class ChatUserProfile(BaseModel):
    """Transport DTO for the chat wire contract -- NOT the authority profile.

    The one authority model is common.profile.UserProfile; this carries only the
    two fields this endpoint's frontend actually sends. It is named distinctly on
    purpose: two different classes both called `UserProfile` is how the profile
    definitions drifted apart in the first place.
    """

    stage: LifecycleStage = DEFAULT_WIRE_STAGE
    # Accepted so the frontend keeps working. Nothing downstream consumes it, and
    # it is deliberately not propagated into the authority profile.
    name: Optional[str] = None

    @field_validator("stage", mode="before")
    @classmethod
    def _map_wire_stage(cls, raw: object) -> LifecycleStage:
        return resolve_wire_stage(raw)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    user_profile: Optional[ChatUserProfile] = None


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
        # Always an authority LifecycleStage value by this point.
        profile = request.user_profile
        user_stage = (profile.stage if profile else DEFAULT_WIRE_STAGE).value

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
