"""Exercises the career planning tool's S7: the render view, the reply
guardrail, the re-render and template fallback, and save suggestions."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.specialist.career_planning.interface import plan_career
from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched
from app.tools.specialist.career_planning.s7_presentation import guardrail, renderer
from app.tools.specialist.career_planning.s7_presentation.payload import to_render_view
from app.tools.specialist.career_planning.s7_presentation.save_suggestions import save_suggestions

CATALOG = [
    {"tag": "data_analytics", "name": "Data Analytics", "definition": "Insight from data.",
     "required_skills": ["data_analytics", "programming", "finance"]},
    {"tag": "quantitative_finance", "name": "Quantitative Finance", "definition": "Pricing.",
     "required_skills": ["programming", "finance", "risk_modeling"]},
    {"tag": "cybersecurity", "name": "Cybersecurity", "definition": "Security.",
     "required_skills": ["security", "programming"]},
]
LINKS = [{"code": "FT5005", "title": "Machine Learning for Finance", "tags": ["data_analytics"]}]
FACTS = {"code_level": 3, "tech_stack": ["python", "excel_vba"],
         "function_experience": [{"key": "data_ai", "internship": True}]}
LABELS = {
    "code_level": {"label": "Programming proficiency", "values": {"3": "Has built a complete project with tests"}},
    "tech_stack": {"label": "Tech stack", "values": {"python": "Python", "excel_vba": "Excel / VBA"}},
    "function_experience": {"label": "Functional experience", "values": {"data_ai": "Data / AI"}},
}


def _prefetched(facts=FACTS) -> Prefetched:
    return Prefetched(facts=facts, stage="current", readiness_gaps=[], role_catalog=CATALOG,
                      course_links=LINKS, evidence_labels=LABELS)


def _result(mode="plan", roles=("data_analytics",)):
    return plan_career({
        "mode": mode, "today": date(2026, 10, 13), "target_roles": list(roles),
        "preferred_roles": ["data_analytics"],
        "profile": {**FACTS, "current_courses": ["FT5005"]},
        "situation": {"stage": "current", "expected_grad_term": "AY2027/28 Sem1"},
        "role_catalog": CATALOG, "course_links": LINKS,
    })


# --- render view ---

def test_the_view_shows_evidence_as_the_profile_does():
    view = to_render_view(_result(), _prefetched())
    skills = {s["skill"]: s for s in view["skills"]}
    assert skills["programming"]["status"] == "met"
    assert skills["programming"]["evidence"][0] == "Programming proficiency: Has built a complete project with tests"
    assert "Tech stack: Python" in skills["programming"]["evidence"]
    assert skills["data analytics"]["evidence"][0] == "Functional experience: Data / AI (internship only)"
    assert "Courses in progress: FT5005 Machine Learning for Finance" in skills["data analytics"]["evidence"]
    (role,) = view["roles"]
    assert role["role"] == "Data Analytics" and role["in_your_profile"]
    assert role["your_current_courses_for_role"] == ["FT5005 Machine Learning for Finance"]
    assert 0 <= role["fit_percent"] <= 100


def test_the_view_leaves_audit_data_out():
    view = to_render_view(_result(), _prefetched())
    assert set(view) == {"mode", "roles", "skills", "roadmap", "comparison", "notes", "sources"}
    assert "points" not in str(view) and "stage_results" not in str(view)
    phase = view["roadmap"]["phases"][0]
    assert set(phase) == {"name", "from", "to", "actions", "milestones"}


def test_the_comparison_names_roles_and_skills():
    view = to_render_view(_result("compare", ("data_analytics", "quantitative_finance")), _prefetched())
    assert view["comparison"] == {
        "needed_by_all": ["programming", "finance"],   # in the first role's order
        "needed_only_by": {"Data Analytics": ["data analytics"], "Quantitative Finance": ["risk modelling"]},
    }


# --- guardrail ---

VIEW = {
    "roles": [{"role": "Data Analytics"}],
    "skills": [{"skill": "finance", "evidence": ["Courses in progress: FT5005 Machine Learning for Finance"]}],
    "roadmap": {"phases": [{"from": "2026-12-01", "to": "2027-03-31",
                            "milestones": [{"date": "2027-04-15"}]}]},
}
NAMES = ["Data Analytics", "Quantitative Finance", "Cybersecurity"]


def test_a_faithful_reply_passes():
    reply = ("Data Analytics fits you at 45%. You're taking FT5005. Applications run from December 2026 to "
             "Mar 2027, with offers by 15 April 2027 (2027年4月).")
    assert guardrail.check(reply, VIEW, "", NAMES) == []


@pytest.mark.parametrize("reply, problem", [
    ("Take FT5010 next.", "course codes"),
    ("You might also consider Cybersecurity.", "roles not in the result"),
    ("Applications open in January 2027.", "dates not in the result"),
    ("申请在2027年1月开始。", "dates not in the result"),
    ("Starting salaries are around S$6,000.", "money"),
    ("年薪大约 8 万。", "money"),
])
def test_invented_facts_are_caught(reply, problem):
    assert any(problem in v for v in guardrail.check(reply, VIEW, "", NAMES))


def test_what_the_user_said_may_be_echoed():
    message = "Is Cybersecurity better? I start in January 2027 and want S$6000."
    reply = "Cybersecurity isn't in your results; January 2027 is noted; I can't speak to S$6000."
    assert guardrail.check(reply, VIEW, message, NAMES) == []


def test_a_role_name_that_is_also_a_skill_is_not_stray():
    view = {**VIEW, "skills": [{"skill": "data analytics"}], "roles": [{"role": "Quantitative Finance"}]}
    assert guardrail.check("Your data analytics is partial.", view, "", NAMES) == []


# --- renderer ---

def test_a_failing_reply_is_rendered_again_then_templated(monkeypatch):
    calls = []

    def fake(view, message, style, on_event=None, depth=None):
        calls.append(style)
        return "Consider FT9999.", ["src"]
    monkeypatch.setattr(renderer, "render_structured_reply", fake)
    reply, sources = renderer.render(_result(), _prefetched(), "plan for me")
    assert len(calls) == 2 and "FT9999" in calls[1]
    assert "FT9999" not in reply and "Roles" in reply and sources == ["src"]


def test_a_good_reply_is_kept(monkeypatch):
    monkeypatch.setattr(renderer, "render_structured_reply", lambda *a, **k: ("All good.", []))
    assert renderer.render(_result("exploration", ()), _prefetched(), "what fits me?")[0] == "All good."


def test_each_mode_has_its_style(monkeypatch):
    seen = []
    monkeypatch.setattr(renderer, "render_structured_reply",
                        lambda view, m, style, **k: seen.append(style) or ("ok", []))
    renderer.render(_result("exploration", ()), _prefetched(), "")
    renderer.render(_result("compare", ("data_analytics", "cybersecurity")), _prefetched(), "")
    assert "which roles suit them" in seen[0] and "weighing roles" in seen[1]


# --- save suggestions ---

def test_a_planned_role_and_stated_facts_are_offered():
    parsed = ParsedCareerRequest(roles=["quantitative_finance"], job_search_timeline="right_after",
                                 target_markets=["HK"])
    facts = {"target_markets": ["SG"], "job_search_timeline": "right_after"}
    assert save_suggestions(parsed, _prefetched(facts), "plan") == [
        {"field_key": "main_target_role", "value": "quantitative_finance"},
        {"field_key": "target_markets", "value": ["SG", "HK"]},
    ]


def test_compared_roles_are_offered_as_families():
    parsed = ParsedCareerRequest(roles=["data_analytics", "cybersecurity"])
    facts = {"target_role_families": ["data_analytics"], "main_target_role": "data_analytics"}
    assert save_suggestions(parsed, _prefetched(facts), "compare") == [
        {"field_key": "target_role_families", "value": ["data_analytics", "cybersecurity"]},
    ]


def test_nothing_is_offered_when_the_profile_already_says_it():
    parsed = ParsedCareerRequest(roles=["data_analytics"], internship_status="secured")
    facts = {"main_target_role": "data_analytics", "internship_status": "secured"}
    assert save_suggestions(parsed, _prefetched(facts), "plan") == []
    assert save_suggestions(ParsedCareerRequest(roles=["data_analytics"]), _prefetched({}), "exploration") == []
