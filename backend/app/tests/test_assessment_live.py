"""Against the live database: the values the assessment parser accepts are
still the profile dictionary's, and the catalogue record builds a report
the domain accepts."""

from __future__ import annotations

import os
from datetime import date

import pytest

from app.domains.profile import repository as profile_repository
from app.domains.specialist.assessment import interface as assessment
from app.tools.specialist.assessment.s1_understanding import schema
from app.tools.specialist.assessment.s1_understanding.schema import StatedFacts
from app.tools.specialist.assessment.s2_assembly import builder, prefetch

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)


def test_the_parsers_allowed_values_match_the_profile_dictionary():
    definitions = profile_repository.load_field_definitions()
    for key, allowed in {**schema.SINGLE_CHOICES, **schema.MULTI_CHOICES}.items():
        expected = [v for v in definitions[key]["allowed_values"] if v != "unknown"]
        assert list(allowed) == expected, key
    assert list(schema.TEST_KEYS) == definitions["admission_tests"]["allowed_values"]
    for key, (low, high) in schema.LEVELS.items():
        assert (low, high) == (min(definitions[key]["allowed_values"]), max(definitions[key]["allowed_values"])), key


def test_the_catalogue_record_builds_a_report_the_domain_accepts():
    prefetched = prefetch.prefetch(None, today=date(2026, 10, 16))
    report = builder.build_report(prefetched, StatedFacts(values={"degree_discipline_category": "cs_se"}))
    result = assessment.assess(report)
    assert result["intake_year"] == prefetched.programme["intake_year"]
    assert report["requirements"]["ielts_min"] and report["requirements"]["application_closes"]
