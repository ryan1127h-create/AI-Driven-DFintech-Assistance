"""Exercises the tool's s2_assembly/prerequisites.py: the catalogue's
requirement phrasings read as structure, anything else kept as text."""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s2_assembly.prerequisites import parse


def test_a_single_prerequisite():
    assert parse("Must have passed BMF5332", "") == {"all_of": [["BMF5332"]], "coreq_any_of": [], "unparsed": None}


def test_alternatives_form_one_group():
    assert parse("Must have completed IT5001 or IT5001X", "")["all_of"] == [["IT5001", "IT5001X"]]


def test_both_corequisite_phrasings():
    assert parse("Must have completed IT5001X", "Must concurrently take IT5006") == {
        "all_of": [["IT5001X"]], "coreq_any_of": ["IT5006"], "unparsed": None,
    }
    assert parse("", "Must be concurrently enrolled in IT5001 or IT5001X")["coreq_any_of"] == ["IT5001", "IT5001X"]


def test_separate_clauses_must_all_be_met():
    assert parse("Must have completed FT5005 and Must have completed IT5006", "")["all_of"] == [["FT5005"], ["IT5006"]]


def test_other_wording_is_kept_as_text_not_guessed():
    result = parse("Instructor's consent required", "")
    assert result == {"all_of": [], "coreq_any_of": [], "unparsed": "Instructor's consent required"}


def test_nothing_to_parse():
    assert parse("", "") == {"all_of": [], "coreq_any_of": [], "unparsed": None}
