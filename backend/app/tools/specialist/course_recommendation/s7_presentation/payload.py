"""
S7 — the render view: the part of the domain result the reply is written
from. The domain result also carries audit data (stage_results,
diagnostics, score breakdowns, completed-course lists) meant for logs and
API callers; handing that to the rendering model only adds noise and
tokens, so it stays out of the view.
"""

from __future__ import annotations

_PROGRESS_FIELDS = (
    "core_mandatory_done",
    "core_mandatory_remaining",
    "core_choice_done",
    "core_choice_remaining_count",
    "core_replacement_cautions",
    "capstone_path",
    "elective_units_done",
    "elective_units_target",
    "total_units_done",
    "total_units_target",
)

# `synopsis` and `evidence` are what the reply explains a course with;
# `reason` (their plain-text summary) and `matched_skills` (derived from
# role tags, too coarse to explain anything) stay out, as do
# `offered_terms` — the evidence already says when a course runs in only
# one semester, and listing every course's terms only lengthens the reply.
_COURSE_FIELDS = (
    "course_code",
    "course_title",
    "units",
    "recommended",
    "synopsis",
    "evidence",
    "caution",
    "counts_toward",
    "class_times",
    "course_units",
)

_PLAN_FIELDS = ("term", "study_mode", "unit_budget", "budget_source", "units", "clashes", "projected_progress")


def to_render_view(result: dict) -> dict:
    progress = result.get("degree_progress")
    return {
        "mode": result.get("mode", "degree_overview"),
        "target_role": result.get("target_role"),
        "groups": [
            {
                "label": group["label"],
                "required_pick_count": group["required_pick_count"],
                "note": group.get("note"),
                "courses": [
                    {key: rec[key] for key in _COURSE_FIELDS if key in rec}
                    for rec in group.get("recommendations", [])
                ],
            }
            for group in result.get("groups", [])
        ],
        "degree_progress": (
            {key: progress[key] for key in _PROGRESS_FIELDS if key in progress} if progress else None
        ),
        # A semester plan's summary; None in the other modes.
        "plan": {key: result["plan"][key] for key in _PLAN_FIELDS} if result.get("plan") else None,
        "skill_gaps": result.get("skill_gaps", []),
        "notes": result.get("notes", []),
        "sources": result.get("sources", []),
    }


def course_units(view: dict) -> dict[str, set[int]]:
    """course_code -> the unit counts the reply may give each course the
    view recommends: its units, and its full units when it counts fewer
    this semester (the Capstone)."""
    units: dict[str, set[int]] = {}
    for group in view["groups"]:
        for course in group["courses"]:
            allowed = units.setdefault(course["course_code"], set())
            allowed.add(course["units"])
            if course.get("course_units"):
                allowed.add(course["course_units"])
    return units
