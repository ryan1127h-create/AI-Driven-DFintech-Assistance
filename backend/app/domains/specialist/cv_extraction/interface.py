"""
Public interface of the cv_extraction domain — the only module other
domains are allowed to import from app.domains.specialist.cv_extraction.

Current consumers:
    - app/domains/cv_import/service.py, which passes in the CV text and the
      profile field definitions a CV may fill, then checks what comes back.

Usage:
    from app.domains.specialist.cv_extraction.interface import extract_fields
    raw = extract_fields(cv_text, targets)
"""

from __future__ import annotations

from app.domains.specialist.cv_extraction import extraction_agent

__all__ = ["extract_fields"]


def extract_fields(cv_text: str, targets: list[dict]) -> dict:
    """{field_key: {"value", "quote"}} for the targets the CV states,
    unchecked: quotes may not be verbatim and values may not fit the
    field. Raises ValueError on a reply that isn't a JSON object."""
    if not targets or not cv_text.strip():
        return {}
    return extraction_agent.extract(cv_text, targets)
