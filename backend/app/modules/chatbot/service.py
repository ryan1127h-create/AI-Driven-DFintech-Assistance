"""
Chat service — orchestrates one conversational turn: loads conversation
state + applicant profile, builds the prompt, runs the LangGraph supervisor,
and persists the updated state. This is the "engine" behind the /chat
endpoint (see app/modules/chatbot/api.py), kept independent of FastAPI so it
stays easy to test or reuse from another entry point.

Profile data is read-only here — this module never writes to the profile
module's storage, and only ever reaches it through
app.modules.profile.interface (never its repository/models directly), per
the module-isolation rule: cross-module data only flows through a module's
public interface.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.modules.chatbot.agents.supervisor import supervisor_graph
from app.modules.chatbot.conversation_service import render_summaries
from app.modules.chatbot.repository import get_session_store
from app.modules.profile.interface import TEST_USER_ID, get_lifecycle_stage, get_profile_summary_text


@dataclass
class ChatTurnResult:
    session_id: str
    reply: str
    agent_used: str
    user_message: str
    intents: list[str] = field(default_factory=list)


def run_turn(session_id: str | None, message: str) -> ChatTurnResult:
    """
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries (see app/modules/chatbot/repository.py). This is never a
      full-history read: the row itself stays small regardless of how long
      the conversation has run.
    - Reads the applicant's profile (read-only — see module docstring) and
      derives user_stage from its lifecycle_stage, since there is no login
      to source it from per-request.
    - Prepends the profile summary and the history-block summaries, then
      the raw tail, then the new message.
    - Runs the LangGraph supervisor.
    - Persists the updated state (raw tail grows by one turn).

    The caller (see app/modules/chatbot/api.py) is responsible for
    scheduling the post-turn background task (block-freezing) — that needs
    FastAPI's BackgroundTasks, which this function deliberately knows
    nothing about. There is no profile-update background task any more:
    the profile is populated only via the resume-upload endpoint (see
    app/modules/profile/api.py), never from conversation turns.
    """
    session_id = session_id or str(uuid.uuid4())
    store = get_session_store()
    state = store.get_state(session_id)

    new_message = HumanMessage(content=message)

    profile_text = get_profile_summary_text(TEST_USER_ID)
    user_stage = get_lifecycle_stage(TEST_USER_ID) or "prospect"
    summaries_text = render_summaries(state.history_summaries)

    system_blocks = []
    if profile_text:
        system_blocks.append(SystemMessage(content=profile_text))
    if summaries_text:
        system_blocks.append(SystemMessage(content=summaries_text))

    llm_messages = system_blocks + state.raw_tail + [new_message]

    result = supervisor_graph.invoke({
        "messages": llm_messages,
        "user_stage": user_stage,
        "agent_used": "",
        "reply": "",
    })

    # result["messages"] is llm_messages plus whatever the graph appended
    # (exactly one AI message) — slice by position rather than equality,
    # since two messages could coincidentally match content.
    new_ai_messages = result["messages"][len(llm_messages):]

    state.turn_count += 1
    state.raw_tail = state.raw_tail + [new_message] + new_ai_messages
    store.save_state(session_id, state)

    return ChatTurnResult(
        session_id=session_id,
        reply=result["reply"],
        agent_used=result["agent_used"],
        user_message=message,
        intents=result.get("intents", []),
    )
