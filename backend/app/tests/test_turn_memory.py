"""Each turn's structured context is remembered for the next: tools record
what they did (ToolAnswer.contexts), the turn's log entry keeps it, the
next turn reads it back as TurnState.previous_turn, and the intent
classifier sees that previous turn when reading a short follow-up."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.domains.conversation import repository, service
from app.domains.conversation.models import ConversationState
from app.orchestrator import classification, turn_service
from app.orchestrator import dispatch
from app.orchestrator.dispatch import merge, requirements
from app.tools.contracts import MissingInputField, ToolAnswer
from app.tools.turn_context import PreviousTurn, TurnState, to_chat_messages

CONTEXT = {
    "tool": "career", "mode": "exploration", "subjects": ["software_engineering", "data_analytics"],
    "awaiting": {"kind": "choose_role", "options": [
        {"key": "software_engineering", "label": "Software Engineering"},
        {"key": "data_analytics", "label": "Data Analytics"},
    ]},
}


@pytest.fixture
def store(monkeypatch):
    memory = repository.InMemoryConversationStore()
    monkeypatch.setattr(service, "get_session_store", lambda: memory)
    return memory


def _turn(state, question, reply, contexts=None):
    extra = {"turn_contexts": contexts} if contexts else {}
    service.record_turn("s1", state, HumanMessage(question), AIMessage(reply, additional_kwargs=extra),
                        ["career"], "career_agent")


# --- recording and reading back ---

def test_a_turns_contexts_are_saved_and_read_back(store):
    state = ConversationState(user_id="u1")
    _turn(state, "what fits me?", "Roles... Which one?", [CONTEXT])
    loaded = store.get_state("s1")
    assert loaded.pending_turn_intents[-1]["contexts"] == [CONTEXT]
    assert service.last_turn(loaded) == {
        "user_message": "what fits me?", "reply": "Roles... Which one?", "intents": ["career"],
        "agent_used": "career_agent", "contexts": [CONTEXT],
    }


def test_the_last_turn_is_the_latest_one(store):
    state = ConversationState(user_id="u1")
    _turn(state, "first", "one", [CONTEXT])
    _turn(state, "second", "two")
    last = service.last_turn(store.get_state("s1"))
    assert last["user_message"] == "second" and last["contexts"] == []


def test_a_new_conversation_has_no_last_turn():
    assert service.last_turn(ConversationState()) is None


def test_a_turn_logged_before_contexts_existed_reads_without_them():
    state = ConversationState(turn_count=1, raw_tail=[HumanMessage("q"), AIMessage("a")],
                              pending_turn_intents=[{"turn": 1, "intents": ["faq"], "agent_used": "faq"}])
    assert service.last_turn(state)["contexts"] == []


def test_the_last_turn_survives_a_freeze(store, monkeypatch):
    monkeypatch.setattr(service.settings, "history_block_size", 2)
    monkeypatch.setattr(service, "summarize_block", lambda messages, log=None, start=1: "summary")
    state = ConversationState(user_id="u1")
    for i in range(3):
        _turn(state, f"q{i}", f"a{i}", [{**CONTEXT, "subjects": [str(i)]}])
    service.freeze_and_unlock("s1")
    last = service.last_turn(store.get_state("s1"))
    assert last["user_message"] == "q2" and last["contexts"][0]["subjects"] == ["2"]
    assert len(store.get_state("s1").history_summaries) == 1   # the freeze did run


# --- what the orchestrator records ---

def test_dispatch_puts_the_contexts_on_the_message(monkeypatch):
    monkeypatch.setattr(dispatch.routing, "route", lambda intents: ("tools", ["career"]))
    monkeypatch.setattr(dispatch.requirements, "check_requirements",
                        lambda names, state: requirements.RequirementsResult(ready=True))
    monkeypatch.setattr(dispatch.execution, "run_tools",
                        lambda names, state, on_event: ToolAnswer(text="hi", contexts=[CONTEXT]))
    state = TurnState(messages=[HumanMessage("x")], user_id="u1")
    ai_message, _, _ = dispatch.answer_turn(state, ["career"])
    assert ai_message.additional_kwargs["turn_contexts"] == [CONTEXT]


def test_a_blocking_card_records_what_it_asked_for():
    result = requirements.RequirementsResult(ready=False, missing=(
        MissingInputField(slot="study_mode", prompt="Full- or part-time?", field_key="study_mode"),
    ))
    (context,) = requirements.build_need_input_answer(result).contexts
    assert context["awaiting"] == {"kind": "fields", "field_keys": ["study_mode"]}


def test_a_consent_card_records_the_consent():
    result = requirements.RequirementsResult(ready=False, missing=(
        MissingInputField(slot="consent:c", prompt="Turn it on", level="required", consent_key="c"),
    ))
    (context,) = requirements.build_need_input_answer(result).contexts
    assert context["awaiting"] == {"kind": "consent", "consent_key": "c"}


def test_a_merged_reply_keeps_every_tools_context():
    partials = [("career", ToolAnswer(text="a", contexts=[CONTEXT])),
                ("faq", ToolAnswer(text="b", contexts=[{"tool": "faq"}]))]
    merged = merge.merge(partials)
    assert merged.contexts == [CONTEXT, {"tool": "faq"}]


# --- the classifier ---

def _previous(**kw) -> PreviousTurn:
    return PreviousTurn(user_message=kw.get("user", "what jobs fit me?"),
                        reply=kw.get("reply", "Here are four roles. " * 30 + "Which one would you like to plan for?"),
                        intents=("career",), agent_used="career_agent", contexts=tuple(kw.get("contexts", [CONTEXT])))


def _sent(monkeypatch, previous):
    seen = {}

    def complete(prompt, user, **kw):
        seen["user"] = user
        return json.dumps({"intents": ["career"], "target_role_hint": "software engineering",
                           "program_hints": [], "reply_language": "zh", "career_mode_hint": "plan"})
    monkeypatch.setattr(classification.llm, "complete", complete)
    result = classification.classify_intent([HumanMessage("软件工程")], previous_turn=previous)
    return seen["user"], result


def test_without_a_previous_turn_only_the_message_is_sent(monkeypatch):
    sent, _ = _sent(monkeypatch, None)
    assert sent == "软件工程"


def test_the_previous_turn_and_its_question_are_sent_before_the_message(monkeypatch):
    sent, result = _sent(monkeypatch, _previous())
    assert sent.startswith("PREVIOUS TURN") and sent.endswith("LATEST MESSAGE (classify this):\n软件工程")
    assert "User: what jobs fit me?" in sent
    assert "Which one would you like to plan for?" in sent and "Here are four roles. " * 30 not in sent
    assert "Answered by: career, mode exploration" in sent
    assert "choose one of these roles: Software Engineering (software_engineering); Data Analytics" in sent
    assert result.intents == ["career"] and result.career_mode_hint == "plan"


def test_a_previous_card_question_is_sent(monkeypatch):
    previous = _previous(contexts=[{"tool": "orchestrator", "mode": "need_input",
                                    "awaiting": {"kind": "fields", "field_keys": ["study_mode"]}}])
    sent, _ = _sent(monkeypatch, previous)
    assert "The assistant asked the user for: study_mode" in sent


def test_the_prompt_explains_how_to_use_the_previous_turn():
    assert "Classify ONLY the LATEST MESSAGE" in classification.INTENT_CLASSIFIER_PROMPT
    assert "reply_language always comes from the LATEST MESSAGE alone" in classification.INTENT_CLASSIFIER_PROMPT


# --- the turn ---

def test_a_turn_hands_the_previous_turn_to_the_classifier_and_the_tools(monkeypatch):
    state = SimpleNamespace(
        history_summaries=[], declined_fields=[], turn_count=1,
        raw_tail=[HumanMessage("what fits me?"), AIMessage("Which one?")],
        pending_turn_intents=[{"turn": 1, "intents": ["career"], "agent_used": "career_agent",
                               "contexts": [CONTEXT]}],
    )
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state)
    monkeypatch.setattr(conv, "record_turn", lambda *a, **k: None)
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "")
    monkeypatch.setattr(turn_service, "get_assistant_preferences",
                        lambda uid: {"language_pref": [], "answer_depth": "standard"})
    seen = {}

    def classify(messages, on_event=None, previous_turn=None):
        seen["classifier"] = previous_turn
        return classification.Classification(["career"], career_mode_hint="plan")
    monkeypatch.setattr(turn_service.classification, "classify_intent", classify)

    def answer_turn(turn_state, intents, on_event=None):
        seen["tools"] = turn_state.previous_turn
        return AIMessage("ok"), "ok", "career_agent"
    monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)

    turn_service.run_turn("s1", "软件工程", "u1")
    assert seen["classifier"] is seen["tools"]
    assert seen["tools"].user_message == "what fits me?" and seen["tools"].awaiting["kind"] == "choose_role"
    assert seen["tools"].context_for("career") == CONTEXT


# --- what goes into prompts ---


def test_the_users_current_record_sits_right_before_their_message(monkeypatch):
    state = SimpleNamespace(history_summaries=[], declined_fields=[], turn_count=1,
                            raw_tail=[HumanMessage("deadline?"), AIMessage("Not in my sources.")],
                            pending_turn_intents=[])
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state)
    monkeypatch.setattr(conv, "record_turn", lambda *a, **k: None)
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "PROFILE")
    monkeypatch.setattr(turn_service, "get_assistant_preferences",
                        lambda uid: {"language_pref": [], "answer_depth": "standard"})
    monkeypatch.setattr(turn_service, "_policy_stage", lambda uid: "admitted")
    monkeypatch.setattr(turn_service.reminders, "deadlines_text", lambda uid: "DATES")
    monkeypatch.setattr(turn_service.classification, "classify_intent",
                        lambda messages, on_event=None, previous_turn=None: classification.Classification(["admissions"]))
    seen = {}

    def answer_turn(turn_state, intents, on_event=None):
        seen["messages"] = [m.content for m in turn_state.messages]
        return AIMessage("ok"), "ok", "admissions_agent"
    monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)

    turn_service.run_turn("s1", "When must I accept?", "u1")
    assert seen["messages"] == ["PROFILE", "deadline?", "Not in my sources.", "DATES", "When must I accept?"]





def test_long_earlier_replies_are_shortened_keeping_start_and_end(monkeypatch):
    monkeypatch.setattr(service.settings, "history_reply_max_chars", 90)
    reply = "START " + "x" * 300 + " Which role?"
    shortened = service.shorten_reply(reply)
    assert len(shortened) < 120 and shortened.startswith("START") and shortened.endswith("Which role?")
    assert "[shortened]" in shortened
    assert service.shorten_reply("short") == "short"
    history = [HumanMessage("q" * 300), AIMessage(reply)]
    prompt = service.for_prompt(history)
    assert prompt[0].content == "q" * 300 and prompt[1].content == shortened


def test_the_summarizer_sees_which_tool_answered_each_turn(monkeypatch):
    seen = {}
    monkeypatch.setattr(service.llm, "complete", lambda prompt, transcript, **k: seen.update(
        prompt=prompt, transcript=transcript) or "summary")
    messages = [HumanMessage("what fits me?"), AIMessage("Four roles."), HumanMessage("SE"), AIMessage("A plan.")]
    log = [{"turn": 5, "intents": ["career"], "agent_used": "career_agent", "contexts": [CONTEXT]},
           {"turn": 6, "intents": ["career"], "agent_used": "career_agent"}]
    assert service.summarize_block(messages, log, start_turn=5) == "summary"
    assert seen["transcript"].splitlines() == [
        "User: what fits me?", "Assistant: Four roles.",
        "[turn 5 answered by career (exploration): software_engineering, data_analytics]",
        "User: SE", "Assistant: A plan.", "[turn 6 answered by career_agent]",
    ]
    assert "current student" in seen["prompt"] and "admissions assistant" not in seen["prompt"]


def test_context_messages_keep_the_system_role():
    roles = [m["role"] for m in to_chat_messages(
        [SystemMessage("profile"), HumanMessage("hi"), AIMessage("hello")])]
    assert roles == ["system", "user", "assistant"]


# --- cache outage ---

class _DownCache:
    def get(self, *a, **k):
        raise ConnectionError("redis down")
    set = delete = get


def test_a_cache_outage_falls_back_to_the_durable_store(monkeypatch):
    durable = repository.InMemoryConversationStore()
    store = repository.CachedConversationStore(durable)
    monkeypatch.setattr(repository, "cache", _DownCache())
    state = ConversationState(user_id="u1", turn_count=1, raw_tail=[HumanMessage("q"), AIMessage("a")])
    store.save_state("s1", state)
    assert store.get_state("s1").raw_tail[0].content == "q"
    store.delete("s1")
    assert durable.get_state("s1").turn_count == 0


def test_programmes_offered_to_choose_from_are_sent(monkeypatch):
    offered = {"tool": "comparison", "mode": "explore", "subjects": ["hku_msc_ftda", "ntu_msc_fintech"],
               "awaiting": {"kind": "choose_programs", "options": [
                   {"key": "hku_msc_ftda", "label": "HKU MSc(FTDA)"}, {"key": "ntu_msc_fintech", "label": "NTU MSc FinTech"}]}}
    previous = PreviousTurn("这个项目和别的学校比怎么样？", "…想挑哪几个对比？", intents=("comparison",), contexts=(offered,))
    sent, _ = _sent(monkeypatch, previous)
    assert "choose programmes to compare with MSc DFT from: HKU MSc(FTDA) (hku_msc_ftda); NTU MSc FinTech" in sent
