"""Exercises the tool's s7_presentation/save_suggestions.py: facts the user
stated this turn that differ from their profile are offered for saving —
only fields the user owns, never ones already on the profile."""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.specialist.course_recommendation.s2_assembly.prefetched import Prefetched
from app.tools.specialist.course_recommendation.s7_presentation.save_suggestions import save_suggestions


def _prefetched(facts: dict, stated_role: str | None = None) -> Prefetched:
    return Prefetched(
        facts=facts, fact_labels={}, role_labels={}, readiness_notes=(), graduation_notes=(),
        role_tag=stated_role, stated_role_tag=stated_role, role_profile=None, courses=[],
        curriculum_rules=[], course_tags={}, role_tags=[], course_electives={},
    )


def test_stated_facts_that_differ_from_the_profile_are_offered():
    parsed = ParsedRequest(
        vertical_preference=["financial_data_analytics_intelligence"],
        capstone_intent="electives_instead", study_mode="part_time",
    )
    facts = {"main_target_role": "product_business", "track_interest": ["computing_technologies"],
             "study_mode": "full_time"}
    assert save_suggestions(parsed, _prefetched(facts, stated_role="data_analytics")) == [
        {"field_key": "main_target_role", "value": "data_analytics"},
        {"field_key": "track_interest", "value": ["computing_technologies", "financial_data_analytics_intelligence"]},
        {"field_key": "capstone_intent", "value": "electives_instead"},
        {"field_key": "study_mode", "value": "part_time"},
    ]


def test_nothing_is_offered_when_the_profile_already_says_so():
    parsed = ParsedRequest(vertical_preference=["computing_technologies"], study_mode="full_time")
    facts = {"main_target_role": "data_analytics", "track_interest": ["computing_technologies"], "study_mode": "full_time"}
    assert save_suggestions(parsed, _prefetched(facts, stated_role="data_analytics")) == []


def test_nothing_is_offered_when_nothing_was_stated():
    assert save_suggestions(ParsedRequest(), _prefetched({})) == []
