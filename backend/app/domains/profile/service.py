"""
Profile service — orchestrates the résumé-upload flow: parse the uploaded
file to plain text, run the extraction agent, persist the result. This is
a one-shot generation, not an incremental merge — each new résumé upload
fully replaces the previous profile (see repository.py::upsert's overwrite
semantics).
"""

from __future__ import annotations

import re

from pydantic import ValidationError as PydanticValidationError

from app.core.errors import NotFoundError, ValidationError
from app.domains.checklist import interface as checklist_interface
from app.domains.profile import repository
from app.domains.profile.constants import PROFILE_FIELDS
from app.domains.profile.resume_agent import extract_profile_from_resume
from app.domains.profile.resume_parser import SUPPORTED_EXTENSIONS, extract_text
from app.domains.profile.schemas import ProfilePatch

_SUPPORTED_SUFFIXES = tuple(f".{ext}" for ext in SUPPORTED_EXTENSIONS)


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


def get_profile(user_id: str) -> dict | None:
    """Returns the stored profile for API display or downstream domains."""
    return repository.get(user_id)


def patch_profile(fields: dict, user_id: str) -> dict | None:
    """Applies user-confirmed profile edits without clearing omitted fields.
    `fields` is expected to already be validated/cleaned by
    schemas.py::ProfilePatch — the only caller of this function is the
    PATCH /profile endpoint (see api.py)."""
    return repository.patch(user_id, fields)


def upsert_profile(fields: dict, user_id: str) -> dict:
    """Creates or replaces a user profile after API schema validation."""
    return repository.upsert(user_id, fields)


def _sanitize_extracted_fields(fields: dict) -> dict:
    """
    Runs LLM-extracted résumé fields through the same validation a
    user-submitted PATCH already goes through (schemas.py::ProfilePatch —
    enum values, numeric ranges, free-text length caps) before they're
    allowed to reach the database. This matters here specifically because
    this text is later re-injected verbatim into the *same user's* own
    chatbot system prompt (see interface.py::render_profile_summary) —
    writing whatever JSON the extraction model happened to return,
    unvalidated, is both a data-quality risk and an unbounded-length/
    indirect-injection one.

    Unlike a human-submitted PATCH (which should hard-fail on a bad
    field), a single field the LLM got wrong shouldn't fail the whole
    résumé upload — so this drops just the offending field(s) and
    retries, rather than rejecting the extraction outright.
    """
    candidate = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
    dropped: set[str] = set()
    while candidate:
        try:
            return ProfilePatch.model_validate(candidate).model_dump(exclude_unset=True)
        except PydanticValidationError as exc:
            bad_keys = {str(err["loc"][0]) for err in exc.errors() if err["loc"]} & candidate.keys()
            if not bad_keys:
                break  # defensive: avoid spinning if a bad_key isn't in candidate
            dropped |= bad_keys
            for key in bad_keys:
                candidate.pop(key, None)
    if dropped:
        print(f"[profile.service] Dropped invalid resume-extracted field(s): {sorted(dropped)}")
    return candidate


def generate_profile_from_resume(file_bytes: bytes, filename: str, user_id: str) -> dict:
    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValidationError("Could not extract any text from the uploaded resume.")

    fields = extract_profile_from_resume(text)
    if "completed_courses" in fields:
        # The LLM's raw output could be a comma-separated string or a list;
        # normalize to a list before it hits ProfilePatch's list[str] field.
        fields["completed_courses"] = _clean_completed_courses(fields["completed_courses"])
    # A résumé upload has no other signal for lifecycle stage — default to
    # "prospect" (a résumé submitted for evaluation implies pre-application).
    fields["lifecycle_stage"] = fields.get("lifecycle_stage") or "prospect"
    fields = _sanitize_extracted_fields(fields)

    return repository.upsert(user_id, fields)


async def generate_profile_from_uploaded_resume(user_id: str) -> dict:
    """
    Pulls the résumé already uploaded under the current user's "Curriculum
    vitae / CV" checklist item — there's no direct-upload path here, so
    profile and checklist can never disagree about which résumé file is
    current — validates its extension, then runs the extraction flow above.
    """
    uploaded = await checklist_interface.get_uploaded_file(checklist_interface.RESUME_ITEM_ID, user_id)
    if uploaded is None:
        raise NotFoundError(
            "No resume found in your checklist yet. Please upload your CV under the checklist first."
        )
    content, file_name, _content_type = uploaded

    if not file_name or not file_name.lower().endswith(_SUPPORTED_SUFFIXES):
        raise ValidationError(
            f"Only {_SUPPORTED_SUFFIXES} resumes are supported, but the file uploaded under the "
            f"checklist CV item is '{file_name}'. Please re-upload your CV there in a supported format."
        )

    return generate_profile_from_resume(content, file_name, user_id)
