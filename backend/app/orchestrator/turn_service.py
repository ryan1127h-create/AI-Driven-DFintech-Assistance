"""
Turn service — orchestrates one conversational turn: loads conversation
state + applicant profile, classifies intent, dispatches to the matched
tool(s), and records the updated state. This is the "engine" behind the
/chat endpoint (see api.py), kept independent of FastAPI so it stays easy
to test or reuse from another entry point.

Conversation state (storage, locking, summarization, listing/history/
rollback) lives entirely in app.domains.conversation — this module only
ever reaches it through conversation.interface, never its repository/
service internals directly, per the module-isolation rule: cross-domain
data only flows through a domain's public interface. Same rule for profile
data, read-only here through profile.interface.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.core import stage_policy
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.domains.auth.interface import get_assistant_preferences, get_audience
from app.domains.conversation import interface as conversation
from app.domains.profile.interface import get_profile_field, get_profile_summary_text
from app.domains.specialist.escalation import interface as escalation
from app.orchestrator import classification, dispatch
from app.orchestrator.turn_metrics import read_agent_used
from app.tools.turn_context import OnEvent, PreviousTurn, TurnState

logger = get_logger(__name__)


@dataclass
class ChatTurnResult:
    session_id: str
    reply: str
    agent_used: str
    user_message: str
    intents: list[str] = field(default_factory=list)
    # See ToolAnswer.card / .supplement_card / .save_suggestions.
    card: dict | None = None
    supplement_card: dict | None = None
    save_suggestions: list[dict] = field(default_factory=list)
    # Shown under the reply: {"kind": "opened", "case": {...}, "resources": [...]}
    # when the turn was passed to staff, {"kind": "offer", "category"} when
    # the user may choose to.
    escalation: dict | None = None


def resolve_reply_language(detected: str | None, preferred: list[str]) -> str:
    """The language the message was written in wins; the user's first
    preferred language only decides when that can't be told (e.g. "ok" or
    a course code), and English when there is no preference either."""
    return detected or (preferred[0] if preferred else "en")


def _policy_stage(user_id: str) -> str:
    """The user's stage for the stage policy; the default stage when the
    profile can't be read (the turn still answers)."""
    try:
        return stage_policy.policy_stage(get_profile_field(user_id, "lifecycle_stage"),
                                         get_profile_field(user_id, "sub_stage"))
    except Exception:
        logger.exception("could not read the lifecycle stage of %s", user_id)
        return stage_policy.DEFAULT_STAGE


def _previous_turn(state) -> PreviousTurn | None:
    last = conversation.last_turn(state)
    if last is None:
        return None
    return PreviousTurn(
        user_message=last["user_message"], reply=last["reply"], intents=tuple(last["intents"]),
        agent_used=last["agent_used"], contexts=tuple(last["contexts"]),
    )


def _record_metrics(session_id: str, user_id: str, intents: list[str], agent_used: str, latency_ms: int) -> None:
    def build() -> dict:
        outcome = read_agent_used(agent_used)
        return {
            "conversation_id": session_id, "user_id": user_id, "audience": get_audience(user_id),
            "intents": list(intents), "agent_used": agent_used, "agents": outcome.agents,
            "failed_agents": outcome.failed_agents, "outcome": outcome.outcome, "latency_ms": latency_ms,
        }

    conversation.record_turn_metrics(build)


def open_escalation(session_id: str, user_id: str, state, offer: dict, agents: list[str]) -> dict | None:
    """Opens (or finds) the case and returns the card for it; None when the
    case couldn't be stored. Never raises: a case is extra to the reply."""
    try:
        case = conversation.open_case(
            {"user_id": user_id, "conversation_id": session_id, "trigger_source": offer["trigger_source"],
             "origin_specialist": escalation.origin_label(agents), "category": offer["category"],
             "priority": offer["priority"]},
            lambda: escalation.summarize(conversation.recent_transcript(state), offer["category"]),
        )
    except Exception:
        logger.exception("could not open a %s case for %s", offer.get("category"), session_id)
        return None
    if case is None:
        return None
    card = {"kind": "opened", "case": case}
    if offer["category"] == "sensitive":
        card["resources"] = escalation.SUPPORT_RESOURCES
    return card


def accept_escalation_offer(session_id: str, user_id: str) -> dict:
    """The user took up the offer the latest turn made: opens the case.
    NotFoundError when that turn made no offer (the button can't open a
    case for a turn that didn't propose one)."""
    state = conversation.get_state(session_id, user_id)
    offer = conversation.escalation_offer(state)
    if not offer:
        raise NotFoundError("There is no request to pass to staff in this conversation.")
    last = conversation.last_turn(state) or {}
    card = open_escalation(session_id, user_id, state, offer, read_agent_used(last.get("agent_used", "")).agents)
    if card is None:
        raise ServiceUnavailableError("Your request couldn't be passed to staff right now. Please try again.")
    return card


def run_turn(
    session_id: str | None, message: str, user_id: str,
    on_event: OnEvent | None = None, declined_fields: list[str] | None = None,
) -> ChatTurnResult:
    """
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries. This is never a full-history read: the row itself stays
      small regardless of how long the conversation has run. Ownership is
      checked/claimed by conversation.get_state() — an existing session
      owned by someone else raises ForbiddenError before any LLM/DB work
      happens.
    - Reads the applicant's profile (read-only) for the profile-summary
      system message (this already includes lifecycle stage when known).
    - Prepends the profile summary and the history-block summaries, then
      the raw tail, then the new message.
    - Classifies intent, then dispatches to the matched tool(s).
    - Records the turn (raw tail grows by one turn).

    The caller (see api.py) is responsible for scheduling the post-turn
    background task (block-freezing) — that needs FastAPI's
    BackgroundTasks, which this function deliberately knows nothing about.

    `on_event`, when given, is forwarded into classification/dispatch to
    report progress ("step") and answer-text ("token") events for the
    streaming endpoint. Every tool treats a missing/None value as "emit
    nothing", so leaving this at its default here (the plain /chat
    endpoint) changes nothing about this function's behavior or return
    value.
    """
    session_id = session_id or conversation.new_session_id()
    state = conversation.get_state(session_id, user_id)
    # Fields the user skipped or dismissed in this reply's card join the
    # session's declined set (saved with the turn by record_turn).
    state.declined_fields = sorted({*state.declined_fields, *(declined_fields or [])})

    new_message = HumanMessage(content=message)

    profile_text = get_profile_summary_text(user_id)
    summaries_text = conversation.render_summaries(state.history_summaries)

    system_blocks = []
    if profile_text:
        system_blocks.append(SystemMessage(content=profile_text))
    if summaries_text:
        system_blocks.append(SystemMessage(content=summaries_text))

    llm_messages = system_blocks + conversation.for_prompt(state.raw_tail) + [new_message]
    previous_turn = _previous_turn(state)

    # The dashboard's response time: classifying plus answering, the part
    # of the turn the user waits on the model for.
    started = time.perf_counter()
    classified = classification.classify_intent(llm_messages, on_event, previous_turn=previous_turn)
    intents = classified.intents
    # Someone in distress may well be classified off-topic; they get a
    # caring conversational reply (and the case below), never the fixed
    # "I only answer programme questions" decline.
    if (classified.escalation or {}).get("category") == "sensitive" and intents == ["off_topic"]:
        intents = ["general"]
    # A case this message opens is opened whatever the answer says, so the
    # answer is told: it acknowledges the hand-off instead of, say, asking
    # for details the staff member will gather themselves.
    if (classified.escalation or {}).get("category") in escalation.OPEN_AT_ONCE:
        llm_messages = llm_messages[:-1] + [SystemMessage(content=escalation.HANDOFF_NOTE), new_message]
    preferences = get_assistant_preferences(user_id)
    turn_state = TurnState(
        messages=llm_messages, user_id=user_id,
        target_role_hint=classified.target_role_hint, program_hints=classified.program_hints,
        course_mode_hint=classified.course_mode_hint, career_mode_hint=classified.career_mode_hint,
        comparison_mode_hint=classified.comparison_mode_hint,
        declined_fields=frozenset(state.declined_fields),
        reply_language=resolve_reply_language(classified.reply_language, preferences["language_pref"]),
        answer_depth=preferences["answer_depth"],
        previous_turn=previous_turn,
        stage=_policy_stage(user_id),
    )
    ai_message, reply, agent_used = dispatch.answer_turn(turn_state, intents, on_event)
    latency_ms = int((time.perf_counter() - started) * 1000)

    # Whether this turn needs a human: open a case now, or offer one (the
    # offer is recorded with the turn, for accept_escalation_offer()).
    outcome = read_agent_used(agent_used)
    decision = escalation.decide(classified.escalation, outcome.outcome, intents)
    offer = None
    if decision is not None:
        offer = {"category": decision.category, "trigger_source": decision.trigger_source, "priority": decision.priority}

    conversation.record_turn(session_id, state, new_message, ai_message, intents, agent_used,
                             escalation_offer=offer if decision and decision.action == "offer" else None)
    _record_metrics(session_id, user_id, intents, agent_used, latency_ms)

    escalation_card = None
    if decision is not None and decision.action == "open":
        # After record_turn: the case's conversation row must exist first.
        escalation_card = open_escalation(session_id, user_id, state, offer, outcome.agents)
    elif decision is not None:
        escalation_card = {"kind": "offer", "category": decision.category}

    extra = ai_message.additional_kwargs or {}
    return ChatTurnResult(
        session_id=session_id, reply=reply, agent_used=agent_used,
        user_message=message, intents=intents,
        card=extra.get("card"), supplement_card=extra.get("supplement_card"),
        save_suggestions=list(extra.get("save_suggestions") or []),
        escalation=escalation_card,
    )
