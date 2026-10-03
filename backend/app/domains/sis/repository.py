"""
SIS repository — pure data access for schema `sis`. Private to the sis
domain; other domains go through interface.py.

Rows with source='DB' come from the registry (seeded, not user-editable);
source='QA' enrollments are ones the user reported themselves in chat.
profile.v_profile folds academic_records, course_enrollments and
applications into the merged profile, so a write here shows up there
without any profile-side write.

sis.application_checklist_items is the school's record of which documents
an application has received (read-only here, shown once the user has
bound that application).

Binding: an application is filed under applicant_email; a user claims an
unclaimed application by its application_no, and only when that email is
their login email (bind_application).
"""

from __future__ import annotations

from app.adapters.sis_db_adapter import sis_db

ENROLLMENT_STATUSES = ("completed", "current", "planned")
ENROLLMENT_SOURCES = ("DB", "QA")

_ENROLLMENT_COLUMNS = ("id", "course_code", "term", "status", "grade_band", "credits", "source", "updated_at")


# academic record

def get_academic_record(user_id: str) -> dict | None:
    return sis_db.fetch_one_dict(
        """
        select study_mode, enrolled_at, track_chosen, academic_standing,
               gpa_current_band, expected_grad_term, graduation_term, updated_at
          from sis.academic_records
         where user_id = %s
        """,
        (user_id,),
    )


# course enrollments

def list_enrollments(user_id: str, status: str | None = None) -> list[dict]:
    where, params = "user_id = %s", [user_id]
    if status is not None:
        if status not in ENROLLMENT_STATUSES:
            raise ValueError(f"unknown enrollment status: {status}")
        where += " and status = %s"
        params.append(status)
    return sis_db.fetch_all_dict(
        f"""
        select {', '.join(_ENROLLMENT_COLUMNS)} from sis.course_enrollments
         where {where}
         order by term nulls first, course_code
        """,
        params,
    )


def upsert_enrollment(
    user_id: str,
    course_code: str,
    *,
    term: str | None,
    status: str,
    source: str,
    grade_band: str | None = None,
    credits=None,
) -> dict:
    """One row per (user, course, term) — a NULL term counts as a value,
    so a re-report of an undated course updates rather than duplicates.
    course_code must exist in knowledge.courses (FK)."""
    if status not in ENROLLMENT_STATUSES:
        raise ValueError(f"unknown enrollment status: {status}")
    if source not in ENROLLMENT_SOURCES:
        raise ValueError(f"unknown enrollment source: {source}")
    return sis_db.fetch_one_dict(
        f"""
        insert into sis.course_enrollments
            (user_id, course_code, term, status, grade_band, credits, source)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (user_id, course_code, term) do update
           set status = excluded.status,
               grade_band = excluded.grade_band,
               credits = excluded.credits,
               source = excluded.source,
               updated_at = now()
        returning {', '.join(_ENROLLMENT_COLUMNS)}
        """,
        (user_id, course_code, term, status, grade_band, credits, source),
    )


def delete_self_reported_enrollment(user_id: str, enrollment_id: str) -> bool:
    """Only source='QA' rows can be removed — registry rows are not the
    user's to delete. Returns False if nothing matched."""
    row = sis_db.execute_returning(
        "delete from sis.course_enrollments where id = %s and user_id = %s and source = 'QA' returning id",
        (enrollment_id, user_id),
    )
    return row is not None


# applications

def list_applications(user_id: str) -> list[dict]:
    """Newest submission first, each with its status_history (oldest change
    first) and the school's document record (documents: [{item_key,
    submitted}] — admissions item keys; their labels live in the knowledge
    schema)."""
    apps = sis_db.fetch_all_dict(
        """
        select application_id, program_id, application_no, application_type,
               admission_term, submission_date, status, final_decision, updated_at
          from sis.applications
         where user_id = %s
         order by submission_date desc nulls last
        """,
        (user_id,),
    )
    if not apps:
        return []
    ids = [a["application_id"] for a in apps]
    history = sis_db.fetch_all_dict(
        """
        select application_id, old_status, new_status, changed_at
          from sis.application_status_history
         where application_id = any(%s)
         order by changed_at
        """,
        (ids,),
    )
    documents = sis_db.fetch_all_dict(
        """
        select application_id, item_key, submitted
          from sis.application_checklist_items
         where application_id = any(%s)
         order by item_key
        """,
        (ids,),
    )
    by_app: dict = {}
    for h in history:
        by_app.setdefault(h.pop("application_id"), []).append(h)
    docs_by_app: dict = {}
    for d in documents:
        docs_by_app.setdefault(d.pop("application_id"), []).append(d)
    for a in apps:
        a["status_history"] = by_app.get(a["application_id"], [])
        a["documents"] = docs_by_app.get(a["application_id"], [])
    return apps


def bind_application(user_id: str, application_no: str, email: str) -> str | None:
    """Links the unclaimed application with this application_no to the
    user, if it was filed under `email` (case-insensitive). Returns its
    application_id, or None when nothing matched — deliberately the same
    for "no such number", "wrong email" and "already claimed"."""
    row = sis_db.execute_returning(
        """
        update sis.applications
           set user_id = %s, updated_at = now()
         where application_no = %s
           and lower(applicant_email) = lower(%s)
           and user_id is null
        returning application_id
        """,
        (user_id, application_no.strip(), email.strip()),
    )
    return str(row[0]) if row else None


def unbind_application(user_id: str, application_id: str) -> bool:
    """Undoes bind_application (used to roll back a binding whose
    follow-up step failed)."""
    row = sis_db.execute_returning(
        """
        update sis.applications set user_id = null, updated_at = now()
         where application_id = %s and user_id = %s
        returning application_id
        """,
        (application_id, user_id),
    )
    return row is not None


# programme

def get_program(program_code: str) -> dict | None:
    return sis_db.fetch_one_dict(
        """
        select program_id, program_code, program_name, program_level, duration_years,
               total_credit_required, description, career_outcomes, tuition_fee, status
          from sis.programs
         where program_code = %s
        """,
        (program_code,),
    )
