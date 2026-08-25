"""
Profile service — orchestrates the resume-upload flow: parse the uploaded
file to plain text, run the extraction agent, persist the result. This is a
one-shot generation, not an incremental merge — each new resume upload fully
replaces the previous profile (see repository.py::upsert's overwrite
semantics).
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from app.modules.profile import repository
from app.modules.profile.agents.resume_agent import extract_profile_from_resume
from app.modules.profile.agents.resume_parser import extract_text
from app.modules.profile.constants import PROFILE_FIELDS, TEST_USER_ID
from app.modules.profile.schemas import ProfilePatch


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


def get_profile(user_id: str = TEST_USER_ID) -> dict | None:
    """Returns the stored profile for API display or downstream modules."""
    return repository.get(user_id)


def patch_profile(fields: dict, user_id: str = TEST_USER_ID) -> dict | None:
    """Applies user-confirmed profile edits without clearing omitted fields.
    `fields` is expected to already be validated/cleaned by
    schemas.py::ProfilePatch — the only caller of this function is the
    PATCH /profile endpoint (see api.py)."""
    return repository.patch(user_id, fields)


def upsert_profile(fields: dict, user_id: str = TEST_USER_ID) -> dict:
    """Creates or replaces a user profile after API schema validation."""
    return repository.upsert(user_id, fields)


def _sanitize_extracted_fields(fields: dict) -> dict:
    """
    Runs LLM-extracted resume fields through the same validation a
    user-submitted PATCH already goes through (schemas.py::ProfilePatch —
    enum values, numeric ranges, free-text length caps) before they're
    allowed to reach the database. This matters here specifically because
    this text is later re-injected verbatim into the *same user's* own
    chatbot system prompt (see
    app/modules/profile/interface.py::render_profile_summary) — writing
    whatever JSON the extraction model happened to return, unvalidated, is
    both a data-quality risk and an unbounded-length/indirect-injection one.

    Unlike a human-submitted PATCH (which should hard-fail with a 422 on a
    bad field), a single field the LLM got wrong shouldn't fail the whole
    resume upload — so this drops just the offending field(s) and retries,
    rather than rejecting the extraction outright.
    """
    candidate = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
    dropped: set[str] = set()
    while candidate:
        try:
            return ProfilePatch.model_validate(candidate).model_dump(exclude_unset=True)
        except ValidationError as exc:
            bad_keys = {str(err["loc"][0]) for err in exc.errors() if err["loc"]} & candidate.keys()
            if not bad_keys:
                break  # defensive: avoid spinning if a bad_key isn't in candidate
            dropped |= bad_keys
            for key in bad_keys:
                candidate.pop(key, None)
    if dropped:
        print(f"[profile.service] Dropped invalid resume-extracted field(s): {sorted(dropped)}")
    return candidate


def generate_profile_from_resume(file_bytes: bytes, filename: str, user_id: str = TEST_USER_ID) -> dict:
    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError("Could not extract any text from the uploaded resume.")

    fields = extract_profile_from_resume(text)
    if "completed_courses" in fields:
        # The LLM's raw output could be a comma-separated string or a list;
        # normalize to a list before it hits ProfilePatch's list[str] field.
        fields["completed_courses"] = _clean_completed_courses(fields["completed_courses"])
    # A resume upload has no other signal for lifecycle stage — default to
    # "prospect" (a résumé submitted for evaluation implies pre-application).
    fields["lifecycle_stage"] = fields.get("lifecycle_stage") or "prospect"
    fields = _sanitize_extracted_fields(fields)

    return repository.upsert(user_id, fields)
