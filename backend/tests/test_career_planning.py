"""Unit tests for career_planning's pure-code parts: the deterministic
fallback plan and the service orchestration (with the LLM, the
recommendation interface, and RAG all stubbed out). No database or LLM."""

from __future__ import annotations

from app.modules.career_planning import service
from app.modules.career_planning.agents import planning_agent

COURSES = [
    {"course_code": "FT5003", "course_title": "Blockchain Systems", "priority": "high", "reason": "Closes gaps."},
    {"course_code": "FT5004", "course_title": "Payments Tech", "priority": "medium", "reason": "Role fit."},
]


class TestFallbackPlan:
    def test_with_profile_role_and_gaps(self):
        plan = planning_agent.fallback_plan("Payments Engineer", ["security"], COURSES, has_profile=True)

        assert "security" in plan["current_fit"]
        assert any("FT5003" in a for a in plan["short_term_actions"])
        assert plan["notes"]  # states the LLM was unavailable

    def test_without_profile_asks_for_resume(self):
        plan = planning_agent.fallback_plan(None, [], [], has_profile=False)

        assert "resume" in plan["current_fit"].lower()
        assert plan["short_term_actions"]  # never empty


class TestServiceOrchestration:
    def stub_dependencies(self, monkeypatch, llm_plan):
        monkeypatch.setattr(service, "get_profile_summary_text", lambda uid: "Profile text")
        monkeypatch.setattr(service, "recommend_courses", lambda user_id, target_role: {
            "target_role": "Payments Engineer",
            "skill_gaps": ["security", "payments_systems"],
            "recommended_courses": COURSES,
            "notes": ["rec note"],
        })
        monkeypatch.setattr(service, "retrieve", lambda *a, **kw: [])
        monkeypatch.setattr(service.planning_agent, "write_plan", lambda **kw: llm_plan)

    def test_uses_llm_plan_when_available(self, monkeypatch):
        self.stub_dependencies(monkeypatch, {
            "current_fit": "Good fit.", "short_term_actions": ["Do X"],
            "medium_term_actions": ["Do Y"], "notes": [],
        })
        result = service.create_career_plan(target_role="payments")

        assert result.current_fit == "Good fit."
        assert result.skill_gaps == ("security", "payments_systems")
        assert result.recommended_courses[0]["course_code"] == "FT5003"
        assert "rec note" in result.notes

    def test_falls_back_when_llm_unavailable(self, monkeypatch):
        self.stub_dependencies(monkeypatch, None)  # write_plan failed
        result = service.create_career_plan(target_role="payments")

        assert result.current_fit  # fallback still produced a plan
        assert any("unavailable" in n for n in result.notes)

    def test_career_mapping_source_always_cited(self, monkeypatch):
        self.stub_dependencies(monkeypatch, None)
        result = service.create_career_plan()

        assert any("Career pathway mapping" in s for s in result.sources)
