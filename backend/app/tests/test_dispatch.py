"""Exercises orchestrator/dispatch.py's routing decisions and its
resilience layers: per-draft evaluate-and-fix (accept/clarify/retry), the
all-branches-failed shortcut, and the top-level safety net in answer_turn()
that turns any uncaught exception into a graceful reply instead of letting
it escape the turn."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.orchestrator import dispatch, routing
from app.tools import localize_tool
from app.tools.contracts import Tool, ToolAnswer, ToolRegistry
from app.tools.evaluate_branch_tool import BranchVerdict
from app.tools.turn_context import TurnState


class _Input(BaseModel):
    model_config = {"arbitrary_types_allowed": True}


def _state(message: str = "What's the tuition fee?", reply_language: str = "en") -> TurnState:
    return TurnState(messages=[HumanMessage(content=message)], user_id="u1", reply_language=reply_language)


def _tool(name: str, intents: frozenset[str], reply: str = "ok") -> Tool:
    return Tool(
        name=name, description=name, input_model=_Input,
        handler=lambda inp, on_event=None: ToolAnswer(text=reply, agent_used=name),
        trigger_intents=intents,
    )


def _accept_verdict(*a, **k):
    return BranchVerdict()


# ---- _route -----------------------------------------------------------

def test_off_topic_alone_declines():
    assert dispatch._route(["off_topic"]) == ("decline", [])


def test_off_topic_mixed_with_a_valid_intent_still_answers_it(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("admissions_tool", frozenset({"admissions"})))
    monkeypatch.setattr(dispatch, "registry", reg)
    assert dispatch._route(["off_topic", "admissions"]) == ("tools", ["admissions_tool"])


def test_no_valid_intents_falls_back_to_general():
    assert dispatch._route([]) == ("general", [])


def test_single_intent_with_no_registered_tool_falls_back_to_general(monkeypatch):
    monkeypatch.setattr(dispatch, "registry", ToolRegistry())
    assert dispatch._route(["admissions"]) == ("general", [])


def test_single_intent_with_a_registered_tool(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("admissions_tool", frozenset({"admissions"})))
    monkeypatch.setattr(dispatch, "registry", reg)
    assert dispatch._route(["admissions"]) == ("tools", ["admissions_tool"])


def test_two_fanout_intents_route_to_both_tools(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("admissions_tool", frozenset({"admissions"})))
    reg.register(_tool("financial_tool", frozenset({"financial"})))
    monkeypatch.setattr(dispatch, "registry", reg)
    mode, names = dispatch._route(["admissions", "financial"])
    assert mode == "tools"
    assert set(names) == {"admissions_tool", "financial_tool"}


# ---- _evaluate_and_fix ---------------------------------------------------

def test_evaluate_and_fix_skips_when_already_needs_clarification(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(dispatch, "registry", reg)
    called = []
    monkeypatch.setattr(reg, "invoke_typed", lambda *a, **k: called.append(1))
    draft = ToolAnswer(text="Which role?", agent_used="career", needs_clarification=True)
    result = dispatch._evaluate_and_fix("career", _state(), "help me plan my career", draft, None)
    assert result is draft
    assert called == []


def test_evaluate_and_fix_respects_the_settings_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "enable_answer_evaluation", False)
    try:
        draft = ToolAnswer(text="Tuition is S$74,120.", agent_used="financial")
        result = dispatch._evaluate_and_fix("financial", _state(), "What's the fee?", draft, None)
        assert result is draft
    finally:
        monkeypatch.setattr(settings, "enable_answer_evaluation", True)


def test_evaluate_and_fix_accept_returns_the_same_draft(monkeypatch):
    reg = ToolRegistry()
    reg.register(Tool(
        name="evaluate_branch", description="d", input_model=BaseModel,
        handler=_accept_verdict, trigger_intents=frozenset(),
    ))
    monkeypatch.setattr(dispatch, "registry", reg)
    draft = ToolAnswer(text="Tuition is S$74,120.", agent_used="financial")
    result = dispatch._evaluate_and_fix("financial", _state(), "What's the fee?", draft, None)
    assert result is draft


def test_evaluate_and_fix_clarify_replaces_the_draft(monkeypatch):
    reg = ToolRegistry()
    reg.register(Tool(
        name="evaluate_branch", description="d", input_model=BaseModel,
        handler=lambda inp, on_event=None: BranchVerdict(action="clarify", note="Which intake?"),
        trigger_intents=frozenset(),
    ))
    monkeypatch.setattr(dispatch, "registry", reg)
    draft = ToolAnswer(text="...", agent_used="admissions")
    result = dispatch._evaluate_and_fix("admissions", _state(), "when are deadlines?", draft, None)
    assert result.text == "Which intake?"
    assert result.needs_clarification is True


def test_evaluate_and_fix_retry_reruns_the_same_tool_silently(monkeypatch):
    calls = []

    def _fake_invoke_typed(name, arg, *, on_event=None):
        if name == "evaluate_branch":
            return BranchVerdict(action="retry", note="missed the deadline part")
        calls.append((name, on_event))
        return ToolAnswer(text="better answer", agent_used="admissions")

    reg = ToolRegistry()
    monkeypatch.setattr(reg, "invoke_typed", _fake_invoke_typed)
    monkeypatch.setattr(dispatch, "registry", reg)

    draft = ToolAnswer(text="partial answer", agent_used="admissions")
    result = dispatch._evaluate_and_fix("admissions", _state(), "what are the deadlines?", draft, on_event=lambda e: None)
    assert len(calls) == 1
    assert calls[0][0] == "admissions"
    assert calls[0][1] is None  # retry never streams, even if the original call did
    assert result.text == "better answer"
    assert result.agent_used.endswith("+revised")


def test_evaluate_and_fix_retry_failure_falls_back_to_the_original_draft(monkeypatch):
    def _fake_invoke_typed(name, arg, *, on_event=None):
        if name == "evaluate_branch":
            return BranchVerdict(action="retry", note="gap")
        raise RuntimeError("boom")

    reg = ToolRegistry()
    monkeypatch.setattr(reg, "invoke_typed", _fake_invoke_typed)
    monkeypatch.setattr(dispatch, "registry", reg)

    draft = ToolAnswer(text="partial answer", agent_used="admissions")
    result = dispatch._evaluate_and_fix("admissions", _state(), "q", draft, None)
    assert result is draft


def test_evaluate_and_fix_evaluation_failure_keeps_the_draft(monkeypatch):
    def _boom(name, arg, *, on_event=None):
        raise RuntimeError("rate limited")

    reg = ToolRegistry()
    monkeypatch.setattr(reg, "invoke_typed", _boom)
    monkeypatch.setattr(dispatch, "registry", reg)

    draft = ToolAnswer(text="partial answer", agent_used="admissions")
    result = dispatch._evaluate_and_fix("admissions", _state(), "q", draft, None)
    assert result is draft


# ---- _run_and_synthesize: all-branches-failed shortcut -------------------

def test_all_branches_failing_skips_evaluation_and_synthesis(monkeypatch):
    reg = ToolRegistry()

    def _broken(inp, on_event=None):
        raise RuntimeError("boom")

    reg.register(Tool(name="a", description="a", input_model=_Input, handler=_broken, trigger_intents=frozenset({"a"})))
    reg.register(Tool(name="b", description="b", input_model=_Input, handler=_broken, trigger_intents=frozenset({"b"})))
    monkeypatch.setattr(dispatch, "registry", reg)

    answer = dispatch._run_and_synthesize(["a", "b"], _state(), "What's a and b?", None)
    assert "again" in answer.text.lower() or "try" in answer.text.lower()


def test_run_and_synthesize_evaluates_each_branch_then_calls_synthesize(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a", frozenset({"a"}), reply="a-answer"))
    reg.register(_tool("b", frozenset({"b"}), reply="b-answer"))

    synth_calls = []

    def _fake_invoke_typed(name, arg, *, on_event=None):
        if name == "evaluate_branch":
            return BranchVerdict()  # accept
        if name == "synthesize":
            synth_calls.append(arg.partials)
            return ToolAnswer(text="merged", agent_used="a+b")
        return reg.get(name).handler(arg, on_event=on_event)

    monkeypatch.setattr(reg, "invoke_typed", _fake_invoke_typed)
    monkeypatch.setattr(dispatch, "registry", reg)

    answer = dispatch._run_and_synthesize(["a", "b"], _state(), "What's a and b?", None)
    assert answer.text == "merged"
    assert len(synth_calls) == 1
    names = [name for name, _ in synth_calls[0]]
    assert names == ["a", "b"]


# ---- answer_turn top-level safety net -----------------------------------

def test_answer_turn_never_raises_on_an_internal_exception(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("admissions_tool", frozenset({"admissions"})))
    monkeypatch.setattr(dispatch, "registry", reg)

    def _boom(*a, **k):
        raise RuntimeError("everything is on fire")

    monkeypatch.setattr(dispatch, "_run_tools", _boom)
    ai_message, reply, agent_used = dispatch.answer_turn(_state(), ["admissions"], None)
    assert agent_used == "orchestrator_error"
    assert "sorry" in ai_message.content.lower()
    assert ai_message.content == reply  # no Sources footer on the error reply


def test_answer_turn_declines_off_topic_without_calling_run_tools(monkeypatch):
    called = []
    monkeypatch.setattr(dispatch, "_run_tools", lambda *a, **k: called.append(1))
    ai_message, reply, agent_used = dispatch.answer_turn(_state("write me a poem"), ["off_topic"], None)
    assert called == []
    assert agent_used == "orchestrator_decline"
    assert "DFT" in ai_message.content


def test_answer_turn_general_mode_never_raises(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(routing, "run_general_chat", _boom)
    ai_message, reply, agent_used = dispatch.answer_turn(_state(), [], None)
    assert agent_used == "orchestrator_error"


# ---- localization is applied last, uniformly -----------------------------

def _reg_with_localize(*tools: Tool) -> ToolRegistry:
    reg = ToolRegistry()
    for tool in tools:
        reg.register(tool)
    reg.register(localize_tool.LOCALIZE_TOOL)
    return reg


def test_answer_turn_localizes_the_final_answer_when_language_is_not_english(monkeypatch):
    reg = _reg_with_localize(_tool("financial_tool", frozenset({"financial"})))
    monkeypatch.setattr(dispatch, "registry", reg)
    monkeypatch.setattr(dispatch, "_run_tools", lambda *a, **k: ToolAnswer(text="Tuition is S$74,120.", agent_used="financial_agent"))
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "学费是 S$74,120。")

    ai_message, reply, agent_used = dispatch.answer_turn(_state("学费是多少？", reply_language="zh"), ["financial"], None)
    assert ai_message.content == "学费是 S$74,120。"
    assert agent_used == "financial_agent"


def test_answer_turn_localizes_the_decline_message_too(monkeypatch):
    monkeypatch.setattr(dispatch, "registry", _reg_with_localize())
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "这个问题不在我的服务范围内。")
    ai_message, reply, agent_used = dispatch.answer_turn(
        _state("帮我写首诗", reply_language="zh"), ["off_topic"], None,
    )
    assert ai_message.content == "这个问题不在我的服务范围内。"
    assert agent_used == "orchestrator_decline"


def test_answer_turn_skips_localization_when_english(monkeypatch):
    reg = _reg_with_localize(_tool("financial_tool", frozenset({"financial"})))
    monkeypatch.setattr(dispatch, "registry", reg)
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "unused")
    monkeypatch.setattr(dispatch, "_run_tools", lambda *a, **k: ToolAnswer(text="Tuition is S$74,120.", agent_used="financial_agent"))

    ai_message, reply, agent_used = dispatch.answer_turn(_state(reply_language="en"), ["financial"], None)
    assert ai_message.content == "Tuition is S$74,120."
    assert calls == []
