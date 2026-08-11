"""
Profile service — orchestrates the resume-upload flow: parse the uploaded
file to plain text, run the extraction agent, persist the result. This is a
one-shot generation, not an incremental merge — each new resume upload fully
replaces the previous profile (see repository.py::upsert's overwrite
semantics).
"""

from __future__ import annotations

import re

from app.modules.profile import repository
from app.modules.profile.agents.resume_agent import extract_profile_from_resume
from app.modules.profile.agents.resume_parser import extract_text
from app.modules.profile.constants import TEST_USER_ID


def _clean_completed_courses(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw_items = re.split(r"[,;\n]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return None

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        course = str(item).strip()
        if not course:
            continue
        course = course[:120]
        key = course.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(course)
    return cleaned


def _normalize_profile_fields(fields: dict) -> dict:
    normalized = dict(fields)
    if "completed_courses" in normalized:
        normalized["completed_courses"] = _clean_completed_courses(normalized["completed_courses"])
    return normalized


def get_profile(user_id: str = TEST_USER_ID) -> dict | None:
    """Returns the stored profile for API display or downstream modules."""
    return repository.get(user_id)


def patch_profile(fields: dict, user_id: str = TEST_USER_ID) -> dict | None:
    """Applies user-confirmed profile edits without clearing omitted fields."""
    return repository.patch(user_id, _normalize_profile_fields(fields))


def generate_profile_from_resume(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError("Could not extract any text from the uploaded resume.")

    fields = _normalize_profile_fields(extract_profile_from_resume(text))
    # A resume upload has no other signal for lifecycle stage — default to
    # "prospect" (a résumé submitted for evaluation implies pre-application).
    fields["lifecycle_stage"] = fields.get("lifecycle_stage") or "prospect"

    return repository.upsert(TEST_USER_ID, fields)
