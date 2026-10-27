"""
Lifecycle service — the study record and degree progress of a current or
graduating student. Read-only: the record and enrollments come from the
school's system (schema sis), course titles and elective verticals from the
knowledge base, and the progress numbers from course_recommendation's own
curriculum interpretation, so this page and a course recommendation never
disagree about what is still outstanding.
"""

from __future__ import annotations

from app.core.errors import ForbiddenError
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.lifecycle.schemas import LifecycleResponse
from app.domains.profile import interface as profile_interface
from app.domains.sis import interface as sis
from app.domains.specialist.course_recommendation import interface as course_recommendation

LIFECYCLE_STAGES = ("current", "graduating")
# The one programme this assistant serves.
PROGRAMME_CODE = "DFT"


def _record(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "study_mode": profile_interface.describe_value("study_mode", row["study_mode"]) if row["study_mode"] else None,
        "track": profile_interface.describe_value("track_chosen", row["track_chosen"]) if row["track_chosen"] else None,
        "enrolled_at": row["enrolled_at"],
        "academic_standing": row["academic_standing"],
        "gpa_band": row["gpa_current_band"],
        "expected_grad_term": row["expected_grad_term"],
        "graduation_term": row["graduation_term"],
    }


_CAPSTONE_NOW = {
    "undecided": "not decided yet (the capstone project FT5007 or three more electives)",
    "direct_in_progress": "capstone route chosen; the capstone project is still to be taken",
    "direct_completed": "capstone project completed",
    "elective_alternative_in_progress": "elective route: three more electives replace the capstone project",
    "elective_alternative_complete": "elective route completed",
}
_CAPSTONE_UNDER_WAY = {
    "direct_completed": "the capstone project (FT5007) is in progress this semester",
    "elective_alternative_complete": "the last electives replacing the capstone are in progress this semester",
}


def progress_text(user_id: str) -> str | None:
    """The student's degree progress as plain sentences for the assistant's
    context — the same numbers the lifecycle page shows, so an answer never
    has to work out units itself. None for anyone not current or
    graduating."""
    try:
        view = get_lifecycle(user_id)
    except ForbiddenError:
        return None
    now, after = view.progress.model_dump(), view.projected_progress.model_dump()
    target = now["total_units_target"]

    def units(status: str) -> tuple[int, str]:
        rows = [c for c in view.courses if c.status == status]
        total = int(sum(float(c.units or 0) for c in rows))
        return total, ", ".join(f"{c.course_code}: {int(float(c.units or 0))} units" for c in rows)

    current_units, current_list = units("current")
    planned_units, planned_list = units("planned")
    capstone = (_CAPSTONE_UNDER_WAY.get(after["capstone_path"])
                if after["capstone_path"] != now["capstone_path"] else None) or _CAPSTONE_NOW.get(now["capstone_path"], "")
    lines = [
        "Degree progress (from the school's record, computed by the programme's curriculum rules):",
        f"- Units: {now['total_units_done']} of {target} completed; {current_units} in progress this semester"
        + (f" ({current_list})" if current_list else "")
        + f"; {min(after['total_units_done'], target)} of {target} after this semester.",
    ]
    if planned_units:
        lines.append(f"- Planned for later: {planned_list}; with these the total reaches "
                     f"{min(after['total_units_done'] + planned_units, target)} of {target} units.")
    lines += [
        (f"- Mandatory core: {len(now['core_mandatory_done'])} done, still to take: "
         f"{', '.join(now['core_mandatory_remaining'])}." if now["core_mandatory_remaining"]
         else f"- Mandatory core: all {len(now['core_mandatory_done'])} done."),
        f"- Core choice courses: {len(now['core_choice_done'])} done, {now['core_choice_remaining_count']} still needed.",
        f"- Elective units: {now['elective_units_done']} of {now['elective_units_target']} done; "
        f"{after['elective_units_done']} after this semester.",
        f"- Capstone: {capstone}.",
    ]
    return "\n".join(lines)


def get_lifecycle(user_id: str) -> LifecycleResponse:
    stage = profile_interface.get_profile_field(user_id, "lifecycle_stage")
    if stage not in LIFECYCLE_STAGES:
        raise ForbiddenError("The lifecycle page is for current and graduating students.")

    courses = {row["course_code"]: row for row in knowledge.list_courses()}
    electives = knowledge.list_course_electives()
    catalogue = [
        {"code": code, "units": int(row["module_credit"] or 0), "vertical": electives.get(code, [])}
        for code, row in courses.items()
    ]
    enrollments = sis.list_enrollments(user_id)
    completed = [e["course_code"] for e in enrollments if e["status"] == "completed"]
    current = [e["course_code"] for e in enrollments if e["status"] == "current"]

    program = sis.get_program(PROGRAMME_CODE) or {}
    return LifecycleResponse(
        user_id=user_id,
        lifecycle_stage=stage,
        programme={
            "code": PROGRAMME_CODE,
            "name": program.get("program_name"),
            "total_units_required": program.get("total_credit_required"),
        },
        record=_record(sis.get_academic_record(user_id)),
        courses=[
            {
                "course_code": e["course_code"],
                "title": (courses.get(e["course_code"]) or {}).get("title"),
                "term": e["term"],
                "status": e["status"],
                "grade_band": e["grade_band"],
                "units": e["credits"],
                "requirement_role": course_recommendation.requirement_role(
                    e["course_code"], electives.get(e["course_code"], [])
                ),
            }
            for e in enrollments
        ],
        progress=course_recommendation.compute_degree_progress(catalogue, completed),
        projected_progress=course_recommendation.compute_degree_progress(catalogue, completed + current),
    )
