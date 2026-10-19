"""
Data access for the `alumni` schema: the alumni directory (alumni.profiles)
and students' connection requests (alumni.requests). Pure SQL, no rules —
see service.py.
"""

from __future__ import annotations

import json

from app.adapters.alumni_db_adapter import alumni_db

_PROFILE_COLUMNS = (
    "position", "company", "class_year", "expertise", "bio", "photo_url",
    "contact_email", "contact_phone", "linkedin_url", "listed",
)
_PROFILE_SELECT = """
    select user_id::text, position, company, class_year, expertise, bio, photo_url,
           contact_email, contact_phone, linkedin_url, listed, created_at, updated_at
      from alumni.profiles
"""
_REQUEST_SELECT = """
    select id::text, student_id::text, alumni_id::text, note, status, shared_contact, reply_note,
           created_at, responded_at
      from alumni.requests
"""


def list_profiles(listed_only: bool = False) -> list[dict]:
    where = " where listed" if listed_only else ""
    return alumni_db.fetch_all_dict(_PROFILE_SELECT + where + " order by created_at")


def get_profile(user_id: str) -> dict | None:
    return alumni_db.fetch_one_dict(_PROFILE_SELECT + " where user_id = %s", (user_id,))


def insert_profile(user_id: str, fields: dict) -> dict:
    columns = [c for c in _PROFILE_COLUMNS if c in fields]
    return alumni_db.fetch_one_dict(
        f"insert into alumni.profiles (user_id, {', '.join(columns)}) values (%s, {', '.join(['%s'] * len(columns))})"
        " returning user_id::text",
        [user_id, *(fields[c] for c in columns)],
    )


def update_profile(user_id: str, fields: dict) -> bool:
    columns = [c for c in _PROFILE_COLUMNS if c in fields]
    if not columns:
        return get_profile(user_id) is not None
    row = alumni_db.execute_returning(
        f"update alumni.profiles set {', '.join(f'{c} = %s' for c in columns)}, updated_at = now()"
        " where user_id = %s returning user_id",
        [*(fields[c] for c in columns), user_id],
    )
    return row is not None


def delete_profile(user_id: str) -> bool:
    return alumni_db.execute_returning("delete from alumni.profiles where user_id = %s returning user_id", (user_id,)) is not None


def requests_for_student(student_id: str) -> list[dict]:
    return alumni_db.fetch_all_dict(_REQUEST_SELECT + " where student_id = %s order by created_at desc", (student_id,))


def requests_for_alumnus(alumni_id: str) -> list[dict]:
    return alumni_db.fetch_all_dict(
        _REQUEST_SELECT + " where alumni_id = %s and status <> 'cancelled' order by created_at desc", (alumni_id,)
    )


def get_request(request_id: str) -> dict | None:
    return alumni_db.fetch_one_dict(_REQUEST_SELECT + " where id = %s", (request_id,))


def count_pending_sent(student_id: str) -> int:
    row = alumni_db.fetch_one_dict(
        "select count(*)::int as n from alumni.requests where student_id = %s and status = 'pending'", (student_id,)
    )
    return row["n"] if row else 0


def insert_request(student_id: str, alumni_id: str, note: str | None) -> dict | None:
    """None when an open (pending or accepted) request for the pair already
    exists — the unique index decides, so two clicks can't make two."""
    row = alumni_db.fetch_one_dict(
        """insert into alumni.requests (student_id, alumni_id, note) values (%s, %s, %s)
           on conflict (student_id, alumni_id) where status in ('pending', 'accepted') do nothing
           returning id::text""",
        (student_id, alumni_id, note),
    )
    return get_request(row["id"]) if row else None


def set_request_status(request_id: str, from_status: str, to_status: str,
                       shared_contact: dict | None = None, reply_note: str | None = None) -> dict | None:
    """Moves a request on only if it is still in `from_status` (so a double
    click or a race can't, say, accept a request the student just cancelled)."""
    row = alumni_db.fetch_one_dict(
        """update alumni.requests
              set status = %s, shared_contact = coalesce(%s::jsonb, shared_contact), reply_note = %s,
                  responded_at = case when %s in ('accepted', 'declined') then now() else responded_at end
            where id = %s and status = %s
        returning id::text""",
        (to_status, json.dumps(shared_contact) if shared_contact is not None else None, reply_note,
         to_status, request_id, from_status),
    )
    return get_request(row["id"]) if row else None
