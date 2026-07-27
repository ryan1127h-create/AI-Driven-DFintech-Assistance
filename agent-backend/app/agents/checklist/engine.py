"""#4 Checklist rule engine (pure Python, deterministic).

Decides WHICH documents a profile requires, each document's status, deadline
and urgency. The LLM is never involved in this decision — it only phrases the
`why` later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from common.profile import DegreeClassification, UserProfile

_RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "admissions_rules.json"

# Honours classification ordered best -> worst (index = rank).
_CLASSIFICATION_ORDER = ["first", "second_upper", "second_lower", "third", "pass"]

# A document still needs applicant action when in one of these states.
_OUTSTANDING = {"missing", "rejected"}


@dataclass
class ChecklistItem:
    key: str
    label: str
    required: bool
    status: str  # missing | submitted | under_review | verified | rejected
    why: str
    deadline: str | None = None  # ISO date, if the item is tied to one
    urgency: str | None = None  # None | info | soon | urgent (outstanding only)


def _load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def _is_foreign_institution(profile: UserProfile, rules: dict) -> bool:
    local_kw = rules["local_institution_keywords"]
    inst = (profile.academic_background.institution or "").lower() if profile.academic_background else ""
    if any(kw in inst for kw in local_kw):
        return False
    return profile.country != "SG"


def _english_proof_required(profile: UserProfile, rules: dict) -> bool:
    return profile.country not in rules["english_exempt_countries"]


def _low_experience(profile: UserProfile, rules: dict) -> bool:
    years = profile.work_years or 0
    return years < rules["low_experience_threshold_years"]


def _classification_below(profile: UserProfile, threshold: str) -> bool:
    """True if the applicant's honours class is strictly worse than `threshold`.

    Unknown / missing classification is treated as NOT below (don't over-trigger
    extra requirements on incomplete data — surface via clarification instead).
    """
    ab = profile.academic_background
    cls = ab.degree_classification if ab else None
    if cls is None or cls == DegreeClassification.unknown:
        return False
    if cls.value not in _CLASSIFICATION_ORDER or threshold not in _CLASSIFICATION_ORDER:
        return False
    return _CLASSIFICATION_ORDER.index(cls.value) > _CLASSIFICATION_ORDER.index(threshold)


def _condition_holds(cond_key: str, cond_val, profile: UserProfile, rules: dict) -> bool:
    if cond_key == "foreign_institution":
        return _is_foreign_institution(profile, rules) == cond_val
    if cond_key == "english_proof_required":
        return _english_proof_required(profile, rules) == cond_val
    if cond_key == "low_experience":
        return _low_experience(profile, rules) == cond_val
    if cond_key == "application_type":
        return profile.application_type is not None and profile.application_type.value == cond_val
    if cond_key == "degree_classification_below":
        return _classification_below(profile, cond_val)
    raise _UnknownCondition(cond_key)


class _UnknownCondition(Exception):
    """Raised when a rule references a condition the engine cannot evaluate."""


def _doc_status(key: str, profile: UserProfile) -> str:
    """Resolve a document's status: rich document_status > submitted list > missing."""
    app = profile.application
    if app is None:
        return "missing"
    if key in app.document_status:
        return app.document_status[key].value
    return "submitted" if key in app.submitted_documents else "missing"


def urgency_for(days_left: int) -> str:
    if days_left <= 3:
        return "urgent"
    if days_left <= 7:
        return "soon"
    return "info"


def _deadline_and_urgency(deadline_key: str | None, status: str,
                          profile: UserProfile, today: date) -> tuple[str | None, str | None]:
    if not deadline_key or profile.application is None:
        return None, None
    iso = profile.application.deadlines.get(deadline_key)
    if not iso:
        return None, None
    # Urgency only matters while the item is still outstanding.
    if status not in _OUTSTANDING:
        return iso, None
    try:
        days_left = (date.fromisoformat(iso) - today).days
    except ValueError:
        return iso, None
    return iso, urgency_for(days_left)


@dataclass
class ChecklistResult:
    items: list[ChecklistItem]
    missing_count: int  # legacy: count of status == "missing"
    outstanding_count: int  # missing + rejected (need action)
    unknown_condition: str | None = None


def build_checklist(profile: UserProfile, today: date | None = None) -> ChecklistResult:
    """Compute the personalised document checklist for a profile."""
    rules = _load_rules()
    today = today or date.today()

    items: list[ChecklistItem] = []
    unknown: str | None = None

    def add(spec: dict) -> None:
        status = _doc_status(spec["key"], profile)
        deadline, urgency = _deadline_and_urgency(
            spec.get("deadline_key"), status, profile, today
        )
        required = bool(spec.get("required", True))
        items.append(
            ChecklistItem(
                key=spec["key"], label=spec["label"], required=required,
                status=status, why=spec["why"], deadline=deadline, urgency=urgency if required else None,
            )
        )

    for spec in rules["base_items"]:
        add(spec)

    for spec in rules["conditional_items"]:
        applies = True
        for cond_key, cond_val in spec["applies_when"].items():
            try:
                if not _condition_holds(cond_key, cond_val, profile, rules):
                    applies = False
                    break
            except _UnknownCondition as e:
                unknown = str(e)
                applies = False
                break
        if applies:
            add(spec)

    missing = sum(1 for it in items if it.status == "missing")
    outstanding = sum(1 for it in items if it.required and it.status in _OUTSTANDING)
    return ChecklistResult(
        items=items, missing_count=missing, outstanding_count=outstanding,
        unknown_condition=unknown,
    )
