"""personalization opt-out -> generic recommendation (no skill-gap)."""
from __future__ import annotations

from common.mock_data import get_profile
from agents.navigator.agent import handle


def test_optout_returns_generic_no_skill_gap():
    p = get_profile("1")
    p.consent_flags.personalization = False
    resp = handle(p, {"target_role": "fintech_pm"})
    assert resp.status == "ok"
    assert resp.data["recommended"]                  # still gives modules (progress-aware key)
    assert resp.data.get("skill_gaps") == []         # but NO personalised gap
    assert resp.data.get("personalized") is False


def test_optin_keeps_skill_gap():
    p = get_profile("1")
    p.consent_flags.personalization = True
    resp = handle(p, {"target_role": "fintech_pm"})
    assert resp.data.get("personalized") is True


def test_comparator_optout_drops_synthesis_keeps_facts():
    from agents.comparator.agent import handle as chandle
    p = get_profile("1")
    p.consent_flags.personalization = False
    resp = chandle(p)
    assert resp.data["facts_table"]["rows"]        # objective table still present
    assert resp.data["synthesis"] is None          # personalised zone suppressed
    assert resp.data.get("personalized") is False
