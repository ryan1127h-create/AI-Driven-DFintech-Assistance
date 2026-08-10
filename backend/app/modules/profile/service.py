"""
Profile service — orchestrates the resume-upload flow: parse the uploaded
file to plain text, run the extraction agent, persist the result. This is a
one-shot generation, not an incremental merge — each new resume upload fully
replaces the previous profile (see repository.py::upsert's overwrite
semantics).
"""

from __future__ import annotations

from app.modules.profile import repository
from app.modules.profile.agents.resume_agent import extract_profile_from_resume
from app.modules.profile.agents.resume_parser import extract_text
from app.modules.profile.constants import TEST_USER_ID


def generate_profile_from_resume(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError("Could not extract any text from the uploaded resume.")

    fields = extract_profile_from_resume(text)
    # A resume upload has no other signal for lifecycle stage — default to
    # "prospect" (a résumé submitted for evaluation implies pre-application).
    fields["lifecycle_stage"] = fields.get("lifecycle_stage") or "prospect"

    return repository.upsert(TEST_USER_ID, fields)
