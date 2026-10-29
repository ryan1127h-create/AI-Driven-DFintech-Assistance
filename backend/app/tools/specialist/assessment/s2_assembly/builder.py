"""
S2 — builds the assessment report (domain contracts.AssessmentReport) from
what prefetch gathered and what the message states.

The applicant's facts are the profile's with the message's laid over them:
a value the message states replaces the profile's (it is the newer word),
a list gains the message's items, and a test score replaces the stored one
for the same test. Each fact records where it came from (cv, profile or
message), so the reply can say "according to your CV".

The requirements are MSc DFT's checked catalogue record: the score
minimums, the GMAT/GRE policy (with the GMAT score the FAQ quotes), the
application period, and the official page each follows.

Pure: reads no data.
"""

from __future__ import annotations

import re

from app.tools import certifications
from app.tools.specialist.assessment.s1_understanding.schema import StatedFacts
from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched

# The profile fields the assessment reads (domain contracts.ApplicantFacts).
FACT_FIELDS = (
    "highest_degree", "degree_discipline_category", "bachelor_grad_year", "gpa_band", "english_medium_degree",
    "admission_tests", "code_level", "math_stats_level", "finance_level", "tech_stack", "prior_coursework",
    "total_work_years", "function_experience", "research_output", "certifications", "intake_term",
)
_LIST_FIELDS = frozenset({"tech_stack", "prior_coursework", "function_experience", "certifications"})
_GMAT_SCORE = re.compile(r"\b([2-8]\d0)\b")


def _keys(items) -> list:
    """List items as plain keys (some list fields store {key, ...} items)."""
    return [i.get("key") if isinstance(i, dict) else i for i in items or []]


def _tests(stored, stated) -> list[dict]:
    by_key = {t["key"]: t for t in (stored or []) if isinstance(t, dict) and t.get("key")}
    by_key.update({t["key"]: t for t in stated or []})
    return [{"key": t["key"], "score": t.get("score"), "test_date": t.get("test_date")} for t in by_key.values()]


def applicant_facts(prefetched: Prefetched, stated: StatedFacts) -> dict:
    profile = prefetched.facts
    facts: dict = {}
    sources: dict = {}
    for key in FACT_FIELDS:
        value = profile.get(key)
        if value in (None, "", [], {}):
            continue
        if key == "certifications":
            # A CFA level or FRM Part 1 passed isn't the credential ("cfa_partial").
            facts[key] = [certifications.evidence_key(item) for item in value]
        else:
            facts[key] = _keys(value) if key in _LIST_FIELDS else value
        sources[key] = "cv" if prefetched.fact_sources.get(key) == "CV" else "profile"
    for key, value in stated.values.items():
        if key == "admission_tests":
            facts[key] = _tests(facts.get(key), value)
        elif key in _LIST_FIELDS:
            facts[key] = list(dict.fromkeys([*facts.get(key, []), *value]))
        else:
            facts[key] = value
        sources[key] = "message"
    if "admission_tests" in facts:
        facts["admission_tests"] = _tests(facts["admission_tests"], [])
    if isinstance(facts.get("intake_term"), dict):  # a term stored as {label, ...}
        facts["intake_term"] = facts["intake_term"].get("label")
    return {**facts, "sources": sources}


def _primary_url(programme: dict, field_key: str) -> str | None:
    entries = (programme.get("sources") or {}).get(field_key) or []
    return next((e["source_url"] for e in entries if e.get("role") == "primary"), None)


def requirements(programme: dict) -> dict:
    facts = programme.get("facts") or {}
    deadline = next((d for d in programme.get("deadlines") or [] if d.get("applicant_category") == "all"), None) \
        or next(iter(programme.get("deadlines") or []), None)
    gmat = _GMAT_SCORE.search(facts.get("gmat_gre_note") or "")
    urls = {
        "english": _primary_url(programme, "toefl_ibt_min") or _primary_url(programme, "ielts_min"),
        "gmat_gre": _primary_url(programme, "gmat_gre_policy"),
        "background": _primary_url(programme, "background_requirement"),
        "deadline": deadline.get("source_url") if deadline else None,
    }
    return {
        "intake_year": programme["intake_year"],
        "toefl_ibt_min": facts.get("toefl_ibt_min"),
        "toefl_band_min": facts.get("toefl_ibt_band_min"),
        "ielts_min": facts.get("ielts_min"),
        "gmat_gre_policy": facts.get("gmat_gre_policy"),
        "gmat_reference": int(gmat.group(1)) if gmat else None,
        "work_exp_policy": facts.get("work_exp_policy"),
        "programming_prereq": facts.get("programming_prereq"),
        "background_requirement": facts.get("background_requirement"),
        "application_opens": str(deadline["opens_on"]) if deadline and deadline.get("opens_on") else None,
        "application_closes": str(deadline["closes_on"]) if deadline and deadline.get("closes_on") else None,
        "source_urls": {k: v for k, v in urls.items() if v},
    }


def build_report(prefetched: Prefetched, stated: StatedFacts) -> dict | None:
    """The report for the domain's assess(); None without the programme's
    requirements (nothing to assess against)."""
    if prefetched.programme is None:
        return None
    return {
        "facts": applicant_facts(prefetched, stated),
        "requirements": requirements(prefetched.programme),
        "today": prefetched.today.isoformat(),
    }
