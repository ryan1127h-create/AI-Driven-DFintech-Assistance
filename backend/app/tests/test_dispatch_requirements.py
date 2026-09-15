"""Exercises orchestrator/dispatch/requirements.py: the pre-execution gate
that blocks the WHOLE batch of matched tools until every one of them has
what its required_input() check says it needs, plus answer_turn()'s
wiring of that gate (never calling execution.run_tools() when the gate
isn't ready).

Same monkeypatching style as test_dispatch.py: patch `contracts.registry`
directly (requirements.py does `from app.tools import contracts`)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.orchestrator import dispatch
from app.orchestrator.dispatch import requirements
from app.tools import contracts
from app.tools.contracts import MissingInputField, Tool, ToolRegistry
from app.tools.turn_context import TurnState


class _Input(BaseModel):
    model_config = {"arbitrary_types_allowed": True}


def _state(message: str = "hello") -> TurnState:
    return TurnState(messages=[HumanMessage(content=message)], user_id="u1")


def _tool(name: str, *, required_input=None) -> Tool:
    return Tool(
        name=name, description=name, input_model=_Input,
        handler=lambda inp, on_event=None: None,
        trigger_intents=frozenset({name}),
        required_input=required_input,
    )


def _always_missing(slot: str, prompt: str):
    return lambda state: (MissingInputField(slot=slot, prompt=prompt),)


def _always_ready(state):
    return ()


# ---- check_requirements ---------------------------------------------------

def test_tool_with_no_required_input_is_always_ready(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a"))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["a"], _state())
    assert result.ready is True
    assert result.missing == ()


def test_tool_missing_a_required_field_is_reported(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("career", required_input=_always_missing("target_role", "Which role?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["career"], _state())
    assert result.ready is False
    assert len(result.missing) == 1
    assert result.missing[0].slot == "target_role"
    assert result.missing[0].prompt == "Which role?"


def test_one_ready_one_missing_blocks_the_whole_batch(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("financial", required_input=_always_ready))
    reg.register(_tool("career", required_input=_always_missing("target_role", "Which role?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["financial", "career"], _state())
    assert result.ready is False
    assert [item.slot for item in result.missing] == ["target_role"]


def test_two_tools_missing_the_same_slot_are_deduplicated(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a", required_input=_always_missing("target_role", "Which role?")))
    reg.register(_tool("b", required_input=_always_missing("target_role", "Which role, exactly?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["a", "b"], _state())
    assert result.ready is False
    assert len(result.missing) == 1
    # First-registered tool's wording wins; not re-derived from the second.
    assert result.missing[0].prompt == "Which role?"


def test_a_failing_required_input_check_is_treated_as_satisfied(monkeypatch):
    def _boom(state):
        raise RuntimeError("profile lookup failed")

    reg = ToolRegistry()
    reg.register(_tool("career", required_input=_boom))
    reg.register(_tool("financial", required_input=_always_ready))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["career", "financial"], _state())
    assert result.ready is True
    assert result.missing == ()


# ---- build_need_input_answer -----------------------------------------------

def test_single_missing_field_reuses_its_prompt_verbatim():
    result = requirements.RequirementsResult(
        ready=False, missing=(MissingInputField(slot="target_role", prompt="Which role?"),),
    )
    answer = requirements.build_need_input_answer(result)
    assert answer.text == "Which role?"
    assert answer.agent_used == "orchestrator_need_input"
    assert answer.needs_clarification is True


def test_multiple_missing_fields_are_listed_as_bullets():
    result = requirements.RequirementsResult(
        ready=False,
        missing=(
            MissingInputField(slot="target_role", prompt="Which role?"),
            MissingInputField(slot="programs", prompt="Which programmes?"),
        ),
    )
    answer = requirements.build_need_input_answer(result)
    assert "Which role?" in answer.text
    assert "Which programmes?" in answer.text
    assert answer.agent_used == "orchestrator_need_input"


# ---- answer_turn wiring: the gate must actually prevent execution ---------

def test_answer_turn_skips_execution_entirely_when_gate_is_not_ready(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("career", required_input=_always_missing("target_role", "Which role?")))
    monkeypatch.setattr(contracts, "registry", reg)

    called = []
    monkeypatch.setattr(dispatch.execution, "run_tools", lambda *a, **k: called.append(1))

    ai_message, reply, agent_used = dispatch.answer_turn(_state(), ["career"], None)

    assert called == [], "execution.run_tools() must not run when the gate blocks the turn"
    assert agent_used == "orchestrator_need_input"
    assert ai_message.content == "Which role?"
    assert reply == "Which role?"


def test_answer_turn_runs_execution_normally_when_gate_is_ready(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("financial", required_input=_always_ready))
    monkeypatch.setattr(contracts, "registry", reg)

    called = []

    def _fake_run_tools(tool_names, state, on_event):
        called.append(tool_names)
        return contracts.ToolAnswer(text="Tuition is S$74,120.", agent_used="financial_agent")

    monkeypatch.setattr(dispatch.execution, "run_tools", _fake_run_tools)

    ai_message, reply, agent_used = dispatch.answer_turn(_state(), ["financial"], None)

    assert called == [["financial"]]
    assert agent_used == "financial_agent"
    assert ai_message.content == "Tuition is S$74,120."
