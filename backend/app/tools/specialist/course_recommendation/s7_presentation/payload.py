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
# role tags, too coarse to explain anything) stay out.
_COURSE_FIELDS = (
    "course_code",
    "course_title",
    "units",
    "recommended",
    "synopsis",
    "evidence",
    "caution",
    "offered_terms",
)


def to_render_view(result: dict) -> dict:
    progress = result.get("degree_progress")
    return {
        "target_role": result.get("target_role"),
        "groups": [
            {
                "label": group["label"],
                "required_pick_count": group["required_pick_count"],
                "note": group.get("note"),
                "courses": [
                    {key: rec.get(key) for key in _COURSE_FIELDS}
                    for rec in group.get("recommendations", [])
                ],
            }
            for group in result.get("groups", [])
        ],
        "degree_progress": (
            {key: progress[key] for key in _PROGRESS_FIELDS if key in progress} if progress else None
        ),
        "skill_gaps": result.get("skill_gaps", []),
        "notes": result.get("notes", []),
        "sources": result.get("sources", []),
    }


def course_units(view: dict) -> dict[str, int]:
    """course_code -> units for every course the view recommends."""
    return {
        course["course_code"]: course["units"]
        for group in view["groups"]
        for course in group["courses"]
    }
