"""Bridge from the chat surface to the profile-driven agents (#4-#7).

The chat surface knows only a lifecycle stage; the four agents advise from a full
UserProfile. This builds the thinnest honest profile chat can supply, calls the
existing supervisor route, and renders the returned envelope as a chat reply.

That envelope was designed for exactly this. common/envelope.py says every agent
returns an AgentResponse "so the (teammate-owned) dialogue module can render
results uniformly" -- but until now the two chains never met, so nothing on the
chat side ever consumed one.

What this deliberately does NOT do is invent profile data. Chat knows a stage and
nothing else, so an answer that depends on the applicant's country, target role or
completed modules is incomplete by construction. The agents already report that
through `missing_fields`, and `render` passes it to the user verbatim instead of
guessing on their behalf.

No langchain or langgraph imports live here, so this is testable in an environment
without them; the graph nodes in app/agents/supervisor.py are thin wrappers.
"""
from __future__ import annotations

from common.envelope import AgentResponse
from common.profile import LifecycleStage, UserProfile
from supervisor import route

CHAT_USER_ID = "chat_user"

# Chat-side intent -> the supervisor's own intent name. Only intents whose answer
# is *about the user* belong here; general programme questions stay with the RAG
# agents, which is what they are good at.
#
# Every target below takes `slots` optionally and defaults sensibly without them
# (comparator falls back to its default weighting, navigator reads the role off
# the profile), so chat can call them with a profile alone.
PERSONALISED_INTENTS: dict[str, str] = {
    "my_documents": "generate_application_checklist",   # #4
    "my_status": "get_application_status",              # #5
    "my_comparison": "compare_programs",                # #6
    "my_courses": "recommend_courses",                  # #7
    "my_career": "recommend_career_path",               # #7
}

# Two supervisor intents are deliberately NOT reachable from chat:
#   check_missing_documents — the same handler as generate_application_checklist,
#     so `my_documents` already covers what a user would ask for.
#   configure_reminders — it writes preferences (channel, frequency) and would
#     need a multi-turn form; a chat turn cannot supply that safely.

_PROFILE_FORM_HINT = (
    "You can fill in the profile form for a tailored answer, or just tell me here "
    "and I will work with what you give me."
)


def profile_from_chat(stage: str, user_id: str = CHAT_USER_ID) -> UserProfile:
    """The thinnest honest profile the chat surface can supply.

    Chat validates `stage` against LifecycleStage at its own boundary
    (app/api/chat.py resolves the frontend's wire vocabulary first), so an
    unrecognised value arriving here is a wiring error rather than user input --
    raising is the right answer, not defaulting to a stage the user never chose.
    """
    return UserProfile(user_id=user_id, lifecycle_stage=LifecycleStage(stage))


def render(response: AgentResponse) -> str:
    """Render one envelope as a chat reply, naming what is still missing.

    `missing_fields` is the agents' existing way of saying "I answered as far as I
    could"; surfacing it is what keeps a stage-only answer honest rather than
    letting it read as a complete one.
    """
    reply = response.speakable.strip()
    if response.missing_fields:
        wanted = ", ".join(response.missing_fields)
        reply = f"{reply}\n\nTo tailor this I still need: {wanted}. {_PROFILE_FORM_HINT}"
    return reply.strip()


def advise(chat_intent: str, stage: str) -> str:
    """Answer a personalised chat request through the #4-#7 agents.

    Exceptions are deliberately not swallowed here. A KeyError means the graph
    routed an intent this bridge does not serve, and an agent failure means a real
    defect -- both should surface at the chat endpoint's own error boundary rather
    than be quietly rendered as an answer.
    """
    intent = PERSONALISED_INTENTS[chat_intent]
    return render(route(intent, profile_from_chat(stage)))
