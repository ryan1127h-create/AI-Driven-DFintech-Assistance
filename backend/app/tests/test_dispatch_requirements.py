"""Exercises orchestrator/dispatch/requirements.py: the pre-execution gate
that blocks the WHOLE batch of matched tools until every one of them has
what its input_needs() check says it needs, plus answer_turn()'s
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
from app.tools.contracts import MissingInputField, Tool, ToolAnswer, ToolRegistry
from app.tools.turn_context import TurnState


class _Input(BaseModel):
    model_config = {"arbitrary_types_allowed": True}


def _state(message: str = "hello") -> TurnState:
    return TurnState(messages=[HumanMessage(content=message)], user_id="u1")


def _tool(name: str, *, input_needs=None) -> Tool:
    return Tool(
        name=name, description=name, input_model=_Input,
        handler=lambda inp, on_event=None: None,
        trigger_intents=frozenset({name}),
        input_needs=input_needs,
    )


def _always_missing(slot: str, prompt: str):
    return lambda state: (MissingInputField(slot=slot, prompt=prompt),)


def _always_ready(state):
    return ()


# ---- check_requirements ---------------------------------------------------

def test_tool_with_no_input_needs_is_always_ready(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a"))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["a"], _state())
    assert result.ready is True
    assert result.missing == ()


def test_tool_missing_a_required_field_is_reported(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("career", input_needs=_always_missing("target_role", "Which role?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["career"], _state())
    assert result.ready is False
    assert len(result.missing) == 1
    assert result.missing[0].slot == "target_role"
    assert result.missing[0].prompt == "Which role?"


def test_one_ready_one_missing_blocks_the_whole_batch(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("financial", input_needs=_always_ready))
    reg.register(_tool("career", input_needs=_always_missing("target_role", "Which role?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["financial", "career"], _state())
    assert result.ready is False
    assert [item.slot for item in result.missing] == ["target_role"]


def test_two_tools_missing_the_same_slot_are_deduplicated(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a", input_needs=_always_missing("target_role", "Which role?")))
    reg.register(_tool("b", input_needs=_always_missing("target_role", "Which role, exactly?")))
    monkeypatch.setattr(contracts, "registry", reg)

    result = requirements.check_requirements(["a", "b"], _state())
    assert result.ready is False
    assert len(result.missing) == 1
    # First-registered tool's wording wins; not re-derived from the second.
    assert result.missing[0].prompt == "Which role?"


def test_a_failing_input_needs_check_is_treated_as_satisfied(monkeypatch):
    def _boom(state):
        raise RuntimeError("profile lookup failed")

    reg = ToolRegistry()
    reg.register(_tool("career", input_needs=_boom))
    reg.register(_tool("financial", input_needs=_always_ready))
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
    reg.register(_tool("career", input_needs=_always_missing("target_role", "Which role?")))
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
    reg.register(_tool("financial", input_needs=_always_ready))
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


# ---- quick-fill cards ---------------------------------------------------------

def test_a_missing_profile_field_comes_back_as_a_quick_fill_card():
    result = requirements.RequirementsResult(
        ready=False,
        missing=(
            MissingInputField(slot="target_role", prompt="Which role?", field_key="main_target_role"),
            MissingInputField(slot="background", prompt="Tell me about yourself."),
        ),
    )
    answer = requirements.build_need_input_answer(result)
    assert answer.card == {
        "kind": "quick_fill",
        "level": "required",
        "skippable": False,
        "reason": answer.text,
        "fields": [{"slot": "target_role", "field_key": "main_target_role", "prompt": "Which role?"}],
    }


def test_no_card_when_no_missing_field_is_a_profile_field():
    result = requirements.RequirementsResult(
        ready=False, missing=(MissingInputField(slot="background", prompt="Tell me about yourself."),),
    )
    assert requirements.build_need_input_answer(result).card is None


def test_the_card_rides_on_the_ai_message_to_the_client(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("career", input_needs=lambda state: (
        MissingInputField(slot="target_role", prompt="Which role?", field_key="main_target_role"),
    )))
    monkeypatch.setattr(contracts, "registry", reg)

    ai_message, reply, agent_used = dispatch.answer_turn(_state(), ["career"], None)

    assert ai_message.content == "Which role?"
    assert ai_message.additional_kwargs["card"]["fields"][0]["field_key"] == "main_target_role"


def test_career_planning_requires_the_main_target_role(monkeypatch):
    from app.tools import input_needs
    from app.tools.specialist import career_planning_tool

    monkeypatch.setattr(career_planning_tool, "_career_facts", lambda state: {})
    monkeypatch.setattr(input_needs, "missing_purpose_consent", lambda uid, purpose: None)
    [missing] = career_planning_tool.CAREER_TOOL.input_needs(_state())
    assert (missing.field_key, missing.level) == ("main_target_role", "required")


def test_career_planning_without_consent_asks_for_the_consent(monkeypatch):
    # Asking for the role would loop: once saved, it still couldn't be read.
    from app.tools import input_needs
    from app.tools.specialist import career_planning_tool

    monkeypatch.setattr(career_planning_tool, "_career_facts", lambda state: {})
    monkeypatch.setattr(input_needs, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    [missing] = career_planning_tool.CAREER_TOOL.input_needs(_state())
    assert (missing.consent_key, missing.field_key, missing.level) == ("consent_personalized_rec", None, "required")


def test_a_role_named_in_the_message_needs_nothing():
    from app.tools.specialist import career_planning_tool

    state = TurnState(messages=[HumanMessage("plan for a quant")], user_id="u1", target_role_hint="quant")
    assert career_planning_tool.CAREER_TOOL.input_needs(state) == ()


# ---- levels -------------------------------------------------------------------

def _needs(*items):
    return lambda state: items


ROLE_OPTIONAL = MissingInputField(slot="main_target_role", prompt="Which role?", field_key="main_target_role", level="optional")
TRACK_SUPPLEMENT = MissingInputField(slot="track_interest", prompt="Tracks?", field_key="track_interest", level="supplementary")


def test_an_optional_field_blocks_with_a_skippable_card(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("course", input_needs=_needs(ROLE_OPTIONAL)))
    monkeypatch.setattr(contracts, "registry", reg)
    gate = requirements.check_requirements(["course"], _state())
    assert not gate.ready
    card = requirements.build_need_input_answer(gate).card
    assert (card["level"], card["skippable"]) == ("optional", True)


def test_a_declined_optional_field_no_longer_blocks(monkeypatch):
    # The skip loop guard: re-sending with the field declined must go through.
    reg = ToolRegistry()
    reg.register(_tool("course", input_needs=_needs(ROLE_OPTIONAL)))
    monkeypatch.setattr(contracts, "registry", reg)
    state = TurnState(messages=[HumanMessage("courses?")], user_id="u1", declined_fields=frozenset({"main_target_role"}))
    assert requirements.check_requirements(["course"], state).ready


def test_a_required_field_cannot_be_declined(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("career", input_needs=_needs(
        MissingInputField(slot="target_role", prompt="Which role?", field_key="main_target_role"),
    )))
    monkeypatch.setattr(contracts, "registry", reg)
    state = TurnState(messages=[HumanMessage("plan")], user_id="u1", declined_fields=frozenset({"main_target_role"}))
    assert not requirements.check_requirements(["career"], state).ready


def test_supplementary_fields_never_block_and_are_capped(monkeypatch):
    extra = [MissingInputField(slot=k, prompt=k, field_key=k, level="supplementary") for k in ("a", "b", "c")]
    reg = ToolRegistry()
    reg.register(_tool("course", input_needs=_needs(*extra)))
    monkeypatch.setattr(contracts, "registry", reg)
    gate = requirements.check_requirements(["course"], _state())
    assert gate.ready
    card = requirements.build_supplement_card(gate)
    assert card["level"] == "supplementary"
    assert [f["field_key"] for f in card["fields"]] == ["a", "b"]


def test_a_dismissed_supplementary_field_is_not_offered_again(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("course", input_needs=_needs(TRACK_SUPPLEMENT)))
    monkeypatch.setattr(contracts, "registry", reg)
    state = TurnState(messages=[HumanMessage("courses?")], user_id="u1", declined_fields=frozenset({"track_interest"}))
    assert requirements.build_supplement_card(requirements.check_requirements(["course"], state)) is None


def test_the_stricter_level_wins_when_two_tools_need_a_field(monkeypatch):
    reg = ToolRegistry()
    reg.register(_tool("a", input_needs=_needs(ROLE_OPTIONAL)))
    reg.register(_tool("b", input_needs=_needs(
        MissingInputField(slot="main_target_role", prompt="Which role?", field_key="main_target_role"),
    )))
    monkeypatch.setattr(contracts, "registry", reg)
    [missing] = requirements.check_requirements(["a", "b"], _state()).missing
    assert missing.level == "required"


def test_a_consent_need_becomes_a_consent_card():
    result = requirements.RequirementsResult(ready=False, missing=(
        MissingInputField(slot="consent:c", prompt="Turn it on.", consent_key="consent_personalized_rec"),
    ))
    assert requirements.build_need_input_answer(result).card == {
        "kind": "consent", "consent_key": "consent_personalized_rec", "reason": "Turn it on.",
    }


def test_the_supplementary_card_rides_under_a_real_answer(monkeypatch):
    reg = ToolRegistry()
    reg.register(Tool(
        name="course", description="course", input_model=_Input,
        handler=lambda inp, on_event=None: ToolAnswer(text="Take IT5006.", agent_used="course"),
        trigger_intents=frozenset({"course"}), input_needs=_needs(TRACK_SUPPLEMENT), skip_evaluation=True,
    ))
    monkeypatch.setattr(contracts, "registry", reg)
    monkeypatch.setattr(dispatch.routing, "route", lambda intents: ("tools", ["course"]))
    ai_message, reply, _ = dispatch.answer_turn(_state(), ["course"], None)
    assert reply == "Take IT5006."
    assert ai_message.additional_kwargs["supplement_card"]["fields"][0]["field_key"] == "track_interest"
