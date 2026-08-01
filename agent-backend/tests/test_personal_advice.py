"""Chat surface -> #4-#7 agents bridge.

Split deliberately: the bridge itself has no langchain/langgraph imports and is
tested unconditionally, while the graph-wiring tests skip when those packages are
absent, so this file runs in an environment that has only the profile stack.
"""
from __future__ import annotations

import pytest

from app.agents.personal_advice import (
    PERSONALISED_INTENTS,
    advise,
    profile_from_chat,
    render,
)
from common.envelope import AgentResponse
from common.profile import LifecycleStage

# (chat intent, a stage the intent applies to, the agent that must answer it).
# test_the_routing_table_covers_every_wired_intent keeps this in step with the
# bridge, so adding a sixth intent without a row here fails rather than silently
# going untested.
_ROUTED = [
    ("my_documents",  "applicant", "checklist_agent"),
    ("my_status",     "applicant", "tracker_agent"),
    ("my_comparison", "applicant", "comparator_agent"),
    ("my_courses",    "current",   "navigator_agent"),
    ("my_career",     "current",   "navigator_agent"),
]


# ---------- the profile chat can honestly supply ----------
@pytest.mark.parametrize("stage", [s.value for s in LifecycleStage])
def test_every_authority_stage_survives_the_chat_boundary(stage):
    assert profile_from_chat(stage).lifecycle_stage.value == stage


def test_an_unknown_stage_raises_rather_than_defaulting():
    """Chat validates the stage first, so a bad value here is a wiring bug.

    Defaulting would hand someone another stage's advice -- the same silent
    coercion the profile unification removed from the recommendation API.
    """
    with pytest.raises(ValueError):
        profile_from_chat("enrolled")  # a wire word, not an authority stage


# ---------- rendering the envelope ----------
def test_missing_fields_are_named_for_the_user():
    reply = render(AgentResponse(
        speakable="Here is what I can tell you.",
        missing_fields=["academic_background", "country"],
    ))
    assert "Here is what I can tell you." in reply
    assert "academic_background" in reply and "country" in reply


def test_a_complete_answer_carries_no_missing_note():
    reply = render(AgentResponse(speakable="You have submitted everything."))
    assert reply == "You have submitted everything."
    assert "still need" not in reply


# ---------- end to end through the real agents (offline, no LLM) ----------
def test_an_applicant_asking_about_their_documents_reaches_the_checklist_agent():
    reply = advise("my_documents", "applicant")
    assert reply
    # Chat supplies a stage and nothing else, so the checklist cannot be complete;
    # it must say so rather than present a stage-only answer as tailored.
    assert "still need" in reply


def test_a_student_asking_what_to_take_reaches_the_navigator_agent():
    reply = advise("my_courses", "current")
    assert "target role" in reply.lower()
    assert "target_roles" in reply       # the machine-readable gap is surfaced too


# A word that appears in exactly one agent's offline reply (verified across all
# five). Needed because agent_used cannot tell these apart: my_courses and
# my_career are the SAME agent, so an intent pointed at the wrong handler keeps
# the correct label while returning the wrong answer.
_SIGNATURE = {
    "my_documents": "checklist",
    "my_status": "status",
    "my_comparison": "comparison",
    "my_courses": "module",
    "my_career": "career",
}


@pytest.mark.parametrize(("intent", "stage"), [(i, s) for i, s, _ in _ROUTED])
def test_each_intent_is_answered_by_its_own_agent(intent, stage):
    """Prove the answer's origin from its content, not from a hard-coded label.

    Deliberately coupled to agent copy: if an agent's wording changes this fails,
    and re-checking that the intent still reaches the right handler is exactly the
    right thing to do at that point. The alternative -- asserting only the label --
    passes even when an intent is wired to the wrong agent entirely.
    """
    reply = advise(intent, stage).lower()
    assert _SIGNATURE[intent] in reply, f"{intent} reply lacks its own signature"
    for other, word in _SIGNATURE.items():
        if other != intent:
            assert word not in reply, f"{intent} was answered like {other}"


def test_the_signature_map_covers_every_wired_intent():
    assert set(_SIGNATURE) == set(PERSONALISED_INTENTS)


@pytest.mark.parametrize(("intent", "stage"), [(i, s) for i, s, _ in _ROUTED])
def test_every_wired_intent_answers_with_something_usable(intent, stage):
    """No wired intent may return an empty reply, whatever the profile lacks.

    Chat supplies a stage and nothing else, so each agent is answering at its
    least-informed. Returning nothing would be worse than saying what is missing.
    """
    assert advise(intent, stage).strip()


def test_a_comparison_still_gives_facts_when_no_role_is_known():
    """#6 differs from the others: with no target role it drops the personalised
    ranking but still returns the objective programme comparison, so there is no
    missing-fields note to append."""
    reply = advise("my_comparison", "applicant")
    assert "comparison" in reply.lower()
    assert "still need" not in reply


def test_an_intent_this_bridge_does_not_serve_raises():
    """A graph routing an unmapped intent here is a wiring error, not user input."""
    with pytest.raises(KeyError):
        advise("financial", "applicant")


def test_the_bridge_only_claims_intents_the_supervisor_actually_routes():
    from supervisor import _ROUTES

    for supervisor_intent in PERSONALISED_INTENTS.values():
        assert supervisor_intent in _ROUTES


# ---------- graph wiring ----------
def _graph_nodes():
    pytest.importorskip("langgraph")
    pytest.importorskip("langchain_core")
    from app.agents.supervisor import build_supervisor_graph

    graph = build_supervisor_graph().get_graph()
    return {n for n in graph.nodes if not n.startswith("__")}


def test_every_personalised_intent_has_a_node_in_the_graph():
    """Guards the whole set, so wiring a sixth intent without a node fails here."""
    assert set(PERSONALISED_INTENTS) <= _graph_nodes()


def test_the_rag_branches_are_untouched_by_this_addition():
    """The point of adding nodes rather than replacing: general questions still
    go to the RAG agents, which answer them better than a profile-driven one."""
    assert {"admissions", "academic", "financial", "assessment", "supervisor"} <= _graph_nodes()


@pytest.mark.parametrize("intent", sorted(PERSONALISED_INTENTS))
def test_a_personalised_intent_routes_to_its_own_node(intent):
    pytest.importorskip("langgraph")
    from app.agents.supervisor import route_by_intent

    assert route_by_intent({"intent": intent}) == intent


def test_an_unclassifiable_intent_still_falls_back_to_general():
    pytest.importorskip("langgraph")
    from app.agents.supervisor import route_by_intent

    assert route_by_intent({"intent": "nonsense"}) == "general"


def test_the_routing_table_covers_every_wired_intent():
    """Fails if an intent is added to the bridge without a row in _ROUTED."""
    assert {intent for intent, _, _ in _ROUTED} == set(PERSONALISED_INTENTS)


@pytest.mark.parametrize(("intent", "stage", "agent_used"), _ROUTED)
def test_a_personalised_question_reaches_its_agent_through_the_graph(
    monkeypatch, intent, stage, agent_used
):
    """Drive the real graph, not just the routing function.

    Asserting route_by_intent alone passes even when the conditional-edge map has
    no entry for the intent -- the function still returns the right name, it just
    connects to nothing. Only executing the graph catches that, which is why this
    goes through invoke() rather than inspecting the node list.

    Intent classification is stubbed because it is the one step needing an LLM;
    everything after it runs offline against the real agents.
    """
    pytest.importorskip("langgraph")
    from langchain_core.messages import HumanMessage

    from app.agents import supervisor as sup

    monkeypatch.setattr(sup, "classify_intent_node", lambda state: {"intent": intent})

    result = sup.build_supervisor_graph().invoke({
        "messages": [HumanMessage(content="what should I do next?")],
        "user_stage": stage,
    })

    assert result["agent_used"] == agent_used
    assert result["reply"].strip()
    # The label is hard-coded in the node, so it survives a node that calls the
    # wrong bridge intent. The reply's content is what actually proves the origin.
    assert _SIGNATURE[intent] in result["reply"].lower()
