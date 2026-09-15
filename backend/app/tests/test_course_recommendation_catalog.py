"""Exercises pipeline/catalog.py: STAGE 2's course classification.

The IT5003/IT5004/IT5005/IT5008 case is a real one, not hypothetical — see
knowledge.course_electives: these 4 codes are simultaneously tagged as a
Vertical elective AND listed as a core-mandatory replacement candidate.
Classifying them as "core_replacement_candidate" first would make them
vanish from every recommendation slot (replacement status alone never
opens a slot — see degree_progress.py), so `vertical` must be checked
before replacement-candidate status.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.pipeline import catalog


def test_capstone_classified_before_anything_else():
    assert catalog.classify_requirement_role("FT5007", ()) == "capstone"


def test_mandatory_core_classification():
    assert catalog.classify_requirement_role("IT5006", ()) == "core_mandatory"


def test_core_choice_classification():
    assert catalog.classify_requirement_role("FT5001", ()) == "core_choice"


def test_replacement_candidate_with_vertical_becomes_elective():
    """The real IT5003/IT5004/IT5005/IT5008 case: dual real-world identity,
    vertical membership must win so the course stays recommendable."""
    role = catalog.classify_requirement_role("IT5003", ("Vertical #1. Computing Technologies",))
    assert role == "elective"


def test_replacement_candidate_without_vertical_falls_back():
    """Defensive fallback for a hypothetical future replacement candidate
    that carries no vertical tag at all — not triggered by any code today."""
    assert catalog.classify_requirement_role("IT5003", ()) == "core_replacement_candidate"


def test_plain_vertical_course_is_elective():
    assert catalog.classify_requirement_role("FE5108", ("Vertical #3.",)) == "elective"


def test_unclassified_when_no_role_and_no_vertical():
    assert catalog.classify_requirement_role("CS4221", ()) == "unclassified"


def test_course_level_parses_the_numeral():
    assert catalog.course_level("CS4221") == 4000
    assert catalog.course_level("BT5126") == 5000
    assert catalog.course_level("FT5007") == 5000


def test_course_level_none_without_a_numeral():
    assert catalog.course_level("XX") is None


def test_workload_shape_project_heavy():
    # FT5007's real shape: 2 lecture, 0 tutorial, 0 lab, 12 project, 1 prep.
    assert catalog.workload_shape_of((2, 0, 0, 12, 1)) == "project_heavy"


def test_workload_shape_lecture_heavy():
    assert catalog.workload_shape_of((3, 0, 0, 1, 4)) == "lecture_heavy"


def test_workload_shape_balanced_otherwise():
    assert catalog.workload_shape_of((2, 1, 0, 3, 2)) == "balanced"


def test_workload_shape_none_when_missing():
    assert catalog.workload_shape_of(None) is None


def test_is_project_averse_matches_keyword():
    assert catalog.is_project_averse("I'd prefer discussion-based courses, less project work")


def test_is_project_averse_false_when_no_signal():
    assert catalog.is_project_averse(None) is False
    assert catalog.is_project_averse("I enjoy hands-on coding") is False
