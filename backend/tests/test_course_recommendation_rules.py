"""Unit tests for course_recommendation's pure-code parts: the hard
eligibility rules, the fallback ranking, and the validation of the LLM's
picks. No database or LLM involved. Run with:  python -m pytest tests/ -q
(pytest is a dev-only dependency, installed in the local venv but not in
requirements.txt.)"""

from __future__ import annotations

from app.modules.course_recommendation.agents import recommendation_agent, rule_engine
from app.modules.course_recommendation.models import CareerRole, Course


def make_course(
    code: str,
    skills: tuple[str, ...] = (),
    section: str = "Core Courses",
    units: int = 4,
    can_recommend: bool = True,
    description: str = "",
    prerequisite_text: str = "",
    preclusion_text: str = "",
) -> Course:
    return Course(
        code=code, title=f"Course {code}", units=units, faculty="Computing",
        section=section, skills=skills, description=description,
        prerequisite_text=prerequisite_text, preclusion_text=preclusion_text,
        can_recommend=can_recommend, source_url="",
    )


ROLE = CareerRole("fintech_pm", "FinTech PM", ("product", "finance", "data_analytics"))
ROLE_SKILLS = list(ROLE.required_skills)


def build_pool(courses, completed=(), role_skills=ROLE_SKILLS):
    return rule_engine.build_candidate_pool(courses, list(completed), role_skills)


class TestNormalizeCodes:
    def test_uppercases_strips_and_dedups(self):
        codes, non_codes = rule_engine.normalize_codes([" ft5005 ", "FT5005", "bt2101"])
        assert codes == ["FT5005", "BT2101"]
        assert non_codes == []

    def test_titles_kept_separately_not_dropped(self):
        codes, non_codes = rule_engine.normalize_codes(["Machine Learning", "", "FT5005"])
        assert codes == ["FT5005"]
        assert non_codes == ["Machine Learning"]


class TestBuildCandidatePool:
    def test_completed_courses_recognized_and_units_counted(self):
        pool = build_pool([make_course("FT5001", ("finance",)), make_course("FT5002")],
                          completed=["FT5001", "XX9999"])

        assert pool.completed_recognized == ("FT5001",)
        assert pool.completed_unrecognized == ("XX9999",)
        assert pool.completed_units == 4
        assert any("XX9999" in n for n in pool.notes)

    def test_profile_course_titles_land_in_unrecognized(self):
        pool = build_pool([make_course("FT5001")],
                          completed=["Intro to Statistics", "FT5001"])

        assert pool.completed_recognized == ("FT5001",)
        assert pool.completed_unrecognized == ("Intro to Statistics",)

    def test_completed_courses_are_not_eligible(self):
        pool = build_pool([make_course("FT5001"), make_course("FT5002")], completed=["FT5001"])

        assert [c.code for c in pool.eligible] == ["FT5002"]

    def test_skill_gaps_exclude_skills_covered_by_completed(self):
        pool = build_pool([make_course("FT5001", ("finance",)), make_course("FT5002")],
                          completed=["FT5001"])

        assert pool.skill_gaps == ("product", "data_analytics")

    def test_preclusion_against_completed_excludes_candidate(self):
        precluded = make_course(
            "FT5020", preclusion_text="must not have completed FT5001 at a grade of at least D",
        )
        pool = build_pool([make_course("FT5001"), precluded], completed=["FT5001"])

        assert pool.excluded_by_preclusion == (("FT5020", "FT5001"),)
        assert all(c.code != "FT5020" for c in pool.eligible)
        assert any("FT5020" in n for n in pool.notes)

    def test_can_recommend_false_is_never_eligible(self):
        pool = build_pool([make_course("FT5040", can_recommend=False)])

        assert pool.eligible == ()


class TestFallbackScoring:
    def test_each_skill_scores_once_gap_or_role_never_both(self):
        pool = build_pool([make_course("FT5001", ("finance",)), make_course("FT5010", ("product",))],
                          completed=["FT5001"])
        scored = rule_engine.score_candidates(pool, ROLE_SKILLS, [], pool.completed_recognized)

        sc = next(s for s in scored if s.course.code == "FT5010")
        assert sc.matched_gap_skills == ("product",)
        assert sc.matched_role_skills == ()  # not double-counted as a role skill
        assert sc.score == rule_engine.W_GAP_SKILL

    def test_gap_closing_course_outranks_covered_skill_course(self):
        pool = build_pool(
            [make_course("FT5001", ("finance",)), make_course("FT5010", ("product",)),
             make_course("FT5011", ("finance",))],
            completed=["FT5001"],
        )
        scored = rule_engine.score_candidates(pool, ROLE_SKILLS, [], pool.completed_recognized)

        codes = [s.course.code for s in scored]
        assert codes.index("FT5010") < codes.index("FT5011")

    def test_preference_keyword_matches_description(self):
        pool = build_pool(
            [make_course("FT5030", description="Covers digital banking platforms."),
             make_course("FT5031", description="Covers derivatives pricing.")],
            role_skills=[],
        )
        scored = rule_engine.score_candidates(pool, [], ["digital banking"], ())

        assert [s.course.code for s in scored] == ["FT5030"]
        assert scored[0].matched_preferences == ("digital banking",)

    def test_no_signal_falls_back_to_core_courses(self):
        pool = build_pool(
            [make_course("FT5050", section="Core Courses"),
             make_course("FT5051", section="Vertical #1. Computing Technologies")],
            role_skills=[],
        )
        scored = rule_engine.score_candidates(pool, [], [], ())

        assert [s.course.code for s in scored] == ["FT5050"]

    def test_capped_at_max(self):
        courses = [make_course(f"FT51{i:02d}", ("product",))
                   for i in range(rule_engine.MAX_RECOMMENDATIONS + 5)]
        pool = build_pool(courses)
        scored = rule_engine.score_candidates(pool, ROLE_SKILLS, [], ())

        assert len(scored) == rule_engine.MAX_RECOMMENDATIONS

    def test_priority_bands(self):
        assert rule_engine.priority_of(rule_engine.PRIORITY_HIGH_MIN) == "high"
        assert rule_engine.priority_of(rule_engine.PRIORITY_MEDIUM_MIN) == "medium"
        assert rule_engine.priority_of(0.0) == "low"


class TestValidatePicks:
    """Code-side validation of the LLM's course picks (no LLM involved)."""

    def make_pool(self):
        return build_pool([make_course("FT5001"), make_course("FT5002"),
                           make_course("FT5003"), make_course("FT5004")])

    def test_valid_picks_pass_through(self):
        raw = [{"course_code": "ft5001", "priority": "High", "reason": "Fits."},
               {"course_code": "FT5002", "priority": "medium", "reason": "Also fits."},
               {"course_code": "FT5003", "priority": "low", "reason": "Optional."}]
        picks = recommendation_agent.validate_picks(raw, self.make_pool())

        assert [p["course_code"] for p in picks] == ["FT5001", "FT5002", "FT5003"]
        assert picks[0]["priority"] == "high"  # normalised

    def test_hallucinated_and_duplicate_codes_dropped(self):
        raw = [{"course_code": "FT9999", "priority": "high", "reason": "Invented."},
               {"course_code": "FT5001", "priority": "high", "reason": "Real."},
               {"course_code": "FT5001", "priority": "low", "reason": "Duplicate."},
               {"course_code": "FT5002", "priority": "high", "reason": "Real."},
               {"course_code": "FT5003", "priority": "high", "reason": "Real."}]
        picks = recommendation_agent.validate_picks(raw, self.make_pool())

        assert [p["course_code"] for p in picks] == ["FT5001", "FT5002", "FT5003"]

    def test_too_few_valid_picks_returns_none(self):
        raw = [{"course_code": "FT5001", "priority": "high", "reason": "Only one."}]
        assert recommendation_agent.validate_picks(raw, self.make_pool()) is None

    def test_garbage_input_returns_none(self):
        assert recommendation_agent.validate_picks(["nonsense", 42], self.make_pool()) is None
