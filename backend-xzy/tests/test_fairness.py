"""Fairness: country must not affect skill inference or recommendations."""
from __future__ import annotations

from common.mock_data import get_profile
from common.skill_matcher import RuleSkillMatcher, background_text


def test_background_text_country_invariant():
    a = get_profile("1")            # country IN
    b = get_profile("1"); b.country = "SG"
    assert background_text(a) == background_text(b)


def test_skill_inference_country_invariant():
    a = get_profile("1")
    b = get_profile("1"); b.country = "US"
    m = RuleSkillMatcher()
    assert {h.id for h in m.infer_user_skills(a)} == {h.id for h in m.infer_user_skills(b)}
