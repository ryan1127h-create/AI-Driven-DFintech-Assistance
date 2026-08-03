"""Registry of editable data targets.

To support a new data file via natural language, add a pydantic schema in
schemas.py and register one EditableTarget here. extract/audit/author need no
changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from . import schemas

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class EditableTarget:
    name: str
    file_path: Path
    schema: type[BaseModel]
    edit_key: str | None  # which top-level key holds the editable object
    risk: str  # "low" | "medium" | "high"
    description: str  # tells the LLM what this file is


_TARGETS: dict[str, EditableTarget] = {
    "status_translations": EditableTarget(
        name="status_translations",
        file_path=_DATA_DIR / "status_translations.json",
        schema=schemas.StatusTranslations,
        edit_key="translations",
        risk="low",
        description=(
            "Maps application status codes (DRAFT, SUBMITTED, UNDER_REVIEW, "
            "DOCS_REQUIRED, OFFER, WAITLIST, REJECTED, ACCEPTED) to a friendly "
            "human_status and a next_step, both in Chinese."
        ),
    ),
    "admissions_rules": EditableTarget(
        name="admissions_rules",
        file_path=_DATA_DIR / "admissions_rules.json",
        schema=schemas.AdmissionsRules,
        edit_key=None,  # whole-file edits (multiple sections)
        risk="high",
        description=(
            "Application document rules. 'base_items' are always required; "
            "'conditional_items' each have an 'applies_when' that may ONLY use "
            "these conditions: foreign_institution, english_proof_required, "
            "low_experience, application_type. Each item has key/label/why. Also "
            "lists english_exempt_countries, local_institution_keywords, and "
            "low_experience_threshold_years."
        ),
    ),
    # Future: programs_dataset (medium risk).
}


def get_target(name: str) -> EditableTarget:
    if name not in _TARGETS:
        raise KeyError(f"unknown target {name!r}; available: {list(_TARGETS)}")
    return _TARGETS[name]


def all_target_names() -> list[str]:
    return list(_TARGETS)
