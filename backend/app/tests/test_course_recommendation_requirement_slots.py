"""Exercises pipeline/requirement_slots.py: STAGE 4's slot derivation and
cross-slot conflict resolution."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import CandidatePool, Course
from app.domains.specialist.course_recommendation.pipeline import curriculum_structure as cs
from app.domains.specialist.course_recommendation.pipeline import degree_progress, requirement_slots


def _course(
    code: str, requirement_role: str, vertical: tuple[str, ...] = (), units: int = 4,
    skills: tuple[str, ...] = (),
) -> Course:
    return Course(
        code=code,
        title=code,
        units=units,
        section="",
        skills=skills,
        description="",
        prerequisite_text="",
        preclusion_text="",
        can_recommend=True,
        source_url="",
        vertical=vertical,
        requirement_role=requirement_role,  # type: ignore[arg-type]
    )


def _pool(
    eligible: list[Course], completed: tuple[str, ...] = (), completed_units: int = 0,
    skill_gaps: tuple[str, ...] = (),
) -> CandidatePool:
    return CandidatePool(
        eligible=tuple(eligible),
        skill_gaps=skill_gaps,
        completed_recognized=completed,
        completed_unrecognized=(),
        completed_units=completed_units,
    )


def test_mandatory_slot_opens_for_remaining_mandatory_courses():
    all_courses = [_course(c, "core_mandatory") for c in cs.CORE_MANDATORY]
    pool = _pool(all_courses)
    progress = degree_progress.compute(all_courses, (), 0)
    slots = requirement_slots.derive_slots(all_courses, pool, progress)
    mandatory_slots = [s for s in slots if s.slot_type == "core_mandatory"]
    assert len(mandatory_slots) == 1
    assert set(mandatory_slots[0].eligible_candidates) == cs.CORE_MANDATORY
    assert mandatory_slots[0].required_pick_count == 2


def test_core_choice_slot_opens_with_pool_of_eligible_ft50xx():
    all_courses = [_course(c, "core_choice") for c in cs.CORE_CHOICE_POOL]
    pool = _pool(all_courses)
    progress = degree_progress.compute(all_courses, (), 0)
    slots = requirement_slots.derive_slots(all_courses, pool, progress)
    choice_slots = [s for s in slots if s.slot_type == "core_choice"]
    assert len(choice_slots) == 1
    assert set(choice_slots[0].eligible_candidates) == cs.CORE_CHOICE_POOL


def test_one_elective_slot_per_vertical_with_eligible_candidates():
    v1 = "Vertical #1. Computing Technologies"
    v2 = "Vertical #2. Financial Data Analytics and Intelligence"
    electives = [_course("CS4221", "elective", vertical=(v1,)), _course("FE5108", "elective", vertical=(v2,))]
    pool = _pool(electives)
    progress = degree_progress.compute(electives, (), 0)
    slots = requirement_slots.derive_slots(electives, pool, progress)
    elective_slots = {s.label: s for s in slots if s.slot_type == "elective"}
    assert len(elective_slots) == 2


def test_only_one_vertical_carries_the_shared_elective_quota():
    """The core bug fix: 3 Verticals must not each independently claim the
    full remaining elective need — only the best-fit one should."""
    v1, v2 = "Vertical #1. Computing Technologies", "Vertical #2. Financial Data Analytics and Intelligence"
    course_v1 = _course("CS4221", "elective", vertical=(v1,), skills=("data_analytics",))
    course_v2 = _course("FE5108", "elective", vertical=(v2,), skills=("finance",))
    pool = _pool([course_v1, course_v2], skill_gaps=("data_analytics",))
    progress = degree_progress.compute([course_v1, course_v2], (), 0)
    slots = requirement_slots.derive_slots([course_v1, course_v2], pool, progress)
    elective_slots = [s for s in slots if s.slot_type == "elective"]
    assert len(elective_slots) == 2

    pick_counts = sorted(s.required_pick_count for s in elective_slots)
    assert pick_counts[0] == 0  # exactly one secondary...
    assert pick_counts[1] > 0  # ...and exactly one primary — never two primaries

    primary = next(s for s in elective_slots if s.required_pick_count > 0)
    assert "Vertical #1" in primary.label  # covers the skill gap, so it wins


def test_secondary_vertical_slot_still_shows_a_couple_of_optional_candidates():
    v1, v2 = "Vertical #1. Computing Technologies", "Vertical #2. Financial Data Analytics and Intelligence"
    course_v1 = _course("CS4221", "elective", vertical=(v1,), skills=("data_analytics",))
    course_v2 = _course("FE5108", "elective", vertical=(v2,))
    pool = _pool([course_v1, course_v2], skill_gaps=("data_analytics",))
    progress = degree_progress.compute([course_v1, course_v2], (), 0)
    slots = requirement_slots.derive_slots([course_v1, course_v2], pool, progress)
    secondary = next(s for s in slots if s.slot_type == "elective" and s.required_pick_count == 0)
    # 0 required + 2 extra, capped by the 1 candidate that actually exists.
    assert secondary.display_count == 1
    assert secondary.eligible_candidates == ("FE5108",)


def test_capstone_slot_opens_only_once_core_done_and_electives_met():
    electives = [_course(f"EL{i}", "elective") for i in range(3)]
    capstone = _course(cs.CAPSTONE_CODE, "capstone", units=12)
    all_courses = (
        [_course(c, "core_mandatory") for c in cs.CORE_MANDATORY]
        + [_course(c, "core_choice") for c in sorted(cs.CORE_CHOICE_POOL)]
        + electives
        + [capstone]
    )
    completed = (
        tuple(cs.CORE_MANDATORY)
        + tuple(sorted(cs.CORE_CHOICE_POOL))[:3]
        + tuple(c.code for c in electives)
    )
    pool = _pool([capstone], completed=completed, completed_units=40)
    progress = degree_progress.compute(all_courses, completed, 40)
    assert progress.capstone_path == "direct_in_progress"
    slots = requirement_slots.derive_slots(all_courses, pool, progress)
    assert any(s.slot_type == "capstone" for s in slots)


def test_no_slots_when_nothing_is_open():
    """Mirrors the flowchart's noteComplete branch: an advanced student
    with every requirement satisfied sees zero slots, not empty ones."""
    capstone = _course(cs.CAPSTONE_CODE, "capstone", units=12)
    all_courses = (
        [_course(c, "core_mandatory") for c in cs.CORE_MANDATORY]
        + [_course(c, "core_choice") for c in sorted(cs.CORE_CHOICE_POOL)]
        + [capstone]
    )
    completed = tuple(cs.CORE_MANDATORY) + tuple(sorted(cs.CORE_CHOICE_POOL))[:3] + (cs.CAPSTONE_CODE,)
    pool = _pool([], completed=completed, completed_units=40)
    progress = degree_progress.compute(all_courses, completed, 40)
    slots = requirement_slots.derive_slots(all_courses, pool, progress)
    assert slots == ()


def test_dual_vertical_course_is_kept_in_only_one_elective_slot():
    """Defensive guard: no course in today's catalogue has 2 Verticals, but
    if one ever did, it must not be recommended twice as if it were two
    independent opportunities."""
    dual = _course("XX9999", "elective", vertical=("Vertical A", "Vertical B"))
    pool = _pool([dual])
    progress = degree_progress.compute([dual], (), 0)
    slots = requirement_slots.derive_slots([dual], pool, progress)
    total_appearances = sum(1 for s in slots if "XX9999" in s.eligible_candidates)
    assert total_appearances == 1
