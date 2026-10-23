"""The stage policy (app/core/stage_policy.py) and how the dispatcher applies
it: modes narrowed, intents rerouted with a note, fixed replies for intents
that don't apply at the user's stage."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.core import stage_policy
from app.orchestrator import dispatch
from app.orchestrator.dispatch import requirements
from app.orchestrator.turn_metrics import read_agent_used
from app.tools.contracts import ToolAnswer
from app.tools.turn_context import TurnState

HINTS = {"course_recommendation": None, "career": None, "comparison": None}


def test_a_rejected_applicant_is_served_as_a_prospect_again():
    assert stage_policy.policy_stage("applicant", "REJECTED") == "rejected"
    assert stage_policy.policy_stage("applicant", "WAITLIST") == "applicant"
    assert stage_policy.policy_stage(None) == "prospect"
    assert stage_policy.policy_stage("alumni", None) == "alumni"


def test_before_enrolment_course_questions_go_to_programme_knowledge():
    for stage in ("prospect", "rejected", "applicant"):
        plan = stage_policy.plan_turn(stage, ["course_recommendation"], HINTS)
        assert plan.intents == ["academic"] and "not enrolled" in plan.notes["academic"]
        assert "curriculum structure" in plan.search_hints["academic"]


def test_an_admitted_student_plans_the_first_semester():
    plan = stage_policy.plan_turn("admitted", ["course_recommendation"], {**HINTS, "course_recommendation": "degree_overview"})
    assert plan.intents == ["course_recommendation"] and plan.modes["course_recommendation"] == "semester_plan"
    plan = stage_policy.plan_turn("admitted", ["course_recommendation"], {**HINTS, "course_recommendation": "ad_hoc"})
    assert plan.modes["course_recommendation"] == "ad_hoc"


def test_enrolled_students_keep_every_course_mode():
    plan = stage_policy.plan_turn("current", ["course_recommendation"], {**HINTS, "course_recommendation": "degree_overview"})
    assert plan.intents == ["course_recommendation"] and plan.modes["course_recommendation"] == "degree_overview"


def test_alumni_get_programme_knowledge_for_courses_and_career():
    plan = stage_policy.plan_turn("alumni", ["course_recommendation", "career"], HINTS)
    assert plan.intents == ["academic", "faq"]
    assert "alumnus" in plan.notes["academic"] and "mentor" in plan.notes["faq"]


def test_an_assessment_that_no_longer_applies_gets_a_fixed_reply():
    for stage in ("admitted", "current", "graduating", "alumni"):
        plan = stage_policy.plan_turn(stage, ["assessment"], HINTS)
        assert plan.intents == [] and len(plan.replies) == 1
    assert stage_policy.plan_turn("prospect", ["assessment"], HINTS).intents == ["assessment"]
    assert stage_policy.plan_turn("rejected", ["assessment"], HINTS).intents == ["assessment"]


def test_rerouted_intents_merge_with_the_ones_already_asked():
    plan = stage_policy.plan_turn("prospect", ["academic", "course_recommendation"], HINTS)
    assert plan.intents == ["academic"] and "not enrolled" in plan.notes["academic"]


def test_only_a_prospect_is_told_how_to_link_an_application():
    assert "Checklist page" in stage_policy.plan_turn("prospect", ["admissions"], HINTS).notes["admissions"]
    assert stage_policy.plan_turn("applicant", ["admissions"], HINTS).notes == {}


# --- dispatch ----------------------------------------------------------------------

def _state(stage: str) -> TurnState:
    return TurnState(messages=[HumanMessage("x")], user_id="u1", stage=stage)


def test_a_fully_redirected_turn_runs_no_tool(monkeypatch):
    monkeypatch.setattr(dispatch.execution, "run_tools", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    ai_message, reply, agent_used = dispatch.answer_turn(_state("admitted"), ["assessment"])
    assert "already received an offer" in ai_message.content and agent_used == "orchestrator_redirect"
    assert read_agent_used(agent_used).outcome == "answered"  # turn_metrics.outcome has no other fitting value


def test_a_rerouted_tool_is_told_the_situation_and_redirects_follow_the_answer(monkeypatch):
    seen = {}
    monkeypatch.setattr(dispatch.requirements, "check_requirements",
                        lambda names, state: requirements.RequirementsResult(ready=True))

    def run_tools(names, state, on_event):
        seen.update(names=names, notes=state.stage_notes)
        return ToolAnswer(text="Courses are ...", agent_used="academic_agent")
    monkeypatch.setattr(dispatch.execution, "run_tools", run_tools)

    ai_message, _, _ = dispatch.answer_turn(_state("alumni"), ["course_recommendation", "assessment"])
    assert seen["names"] == ["academic"] and "alumnus" in seen["notes"]["academic"]
    assert ai_message.content.startswith("Courses are ...") and "graduate of the programme" in ai_message.content
