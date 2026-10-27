"""sis.document_state: only a required document of an open application is
missing; the English test depends on whether the degree was English-medium."""

import pytest

from app.domains.sis import interface as sis


@pytest.mark.parametrize(("status", "key", "submitted", "required", "english_medium", "state"), [
    ("SUBMITTED", "cv", True, True, None, "received"),
    ("SUBMITTED", "cv", False, True, None, "missing"),
    ("DOCS_REQUIRED", "standardised_test_scores", False, False, None, "optional"),
    ("OFFER", "cv", False, True, None, "not_needed"),
    ("REJECTED", "standardised_test_scores", False, False, None, "not_needed"),
    # the English test: required unless the degree was taught in English
    ("UNDER_REVIEW", "english_proficiency", False, False, False, "missing"),
    ("UNDER_REVIEW", "english_proficiency", False, False, True, "exempt"),
    ("OFFER", "english_proficiency", False, False, True, "exempt"),
    ("OFFER", "english_proficiency", False, False, False, "not_needed"),
    ("UNDER_REVIEW", "english_proficiency", False, False, None, "optional"),
    ("UNDER_REVIEW", "english_proficiency", True, False, True, "received"),
])
def test_document_state(status, key, submitted, required, english_medium, state):
    assert sis.document_state(status, key, submitted, required, english_medium) == state


def test_the_english_test_is_required_only_after_a_degree_not_taught_in_english():
    assert sis.required_for("english_proficiency", False, False) is True
    assert sis.required_for("english_proficiency", False, True) is False
    assert sis.required_for("english_proficiency", False, None) is False  # unknown: the catalogue's flag
    assert sis.required_for("cv", True, True) is True
