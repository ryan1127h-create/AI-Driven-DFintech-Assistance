"""#4 Checklist rule engine (pure Python, deterministic).

Decides WHICH documents a profile requires, each document's status, deadline
and urgency. The LLM is never involved in this decision — it only phrases the
`why` later.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from common.profile import UserProfile

_RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "admissions_rules.json"

# Honours classification ordered best -> worst (index = rank).
_CLASSIFICATION_ORDER = ["first", "second_upper", "second_lower", "third", "pass"]

# A document still needs applicant action when in one of these states. This is
# the single definition of "outstanding": this module owns `ChecklistItem.status`,
# so #4's agent and #5's tracker both read the vocabulary from here rather than
# restating it, which is how the three surfaces stay in step.
OUTSTANDING_STATUSES = frozenset({"missing", "rejected"})

_ENGLISH_MEDIUM_KEYWORDS_FIELD = "english_medium_institution_keywords"

# ---------- Requirement level ----------
# Three levels, using the same vocabulary student/profile_form.py already applies
# to the same document set:
#   required    - the applicant must supply it; it blocks the application.
#   conditional - it applies only if a fact the profile does not record is true.
#                 Surfaced so the applicant can confirm, never counted as
#                 blocking: we can neither impose nor waive it from what we have.
#   supporting  - genuinely optional material; nice to have, never chased.
# Collapsing `conditional` into `supporting` would let the system claim an
# application is complete while an unresolved requirement is still open.
REQUIREMENT_REQUIRED = "required"
REQUIREMENT_CONDITIONAL = "conditional"
REQUIREMENT_SUPPORTING = "supporting"
_REQUIREMENT_LEVELS = (REQUIREMENT_REQUIRED, REQUIREMENT_CONDITIONAL, REQUIREMENT_SUPPORTING)

# ---------- Deadline resolution ----------
# The deadline keys that mean "your documents are due by this date", most
# specific first. `offer_acceptance` is deliberately absent: replying to an
# offer is not a document submission, so that date must never be re-labelled as
# a document deadline. A profile carrying no key from this tuple gets no
# deadline at all — making no claim beats inventing one.
_DOCUMENT_DEADLINE_KEYS: tuple[str, ...] = ("application_deadline", "document_deadline")

# Urgency buckets in days left. The thresholds match #5 reminders
# (tracker/reminders.py::_urgency); the past-due bucket is checklist-only.
_URGENT_WITHIN_DAYS = 3
_SOON_WITHIN_DAYS = 7


@dataclass
class ChecklistItem:
    key: str
    label: str
    requirement: str  # required | conditional | supporting
    status: str  # missing | submitted | under_review | verified | rejected
    why: str
    deadline: str | None = None  # ISO date, if the item is tied to one
    urgency: str | None = None  # None | info | soon | urgent | overdue

    @property
    def required(self) -> bool:
        """True only for items that block the application.

        A `conditional` item is deliberately NOT required: the engine cannot tell
        whether it applies, so counting it as blocking would assert a requirement
        the profile does not support.
        """
        return self.requirement == REQUIREMENT_REQUIRED


class _UnknownCondition(Exception):
    """Raised when a rule references a condition the engine cannot evaluate."""


def _load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def _institution_name(profile: UserProfile) -> str:
    ab = profile.academic_background
    return (ab.institution or "").lower() if ab else ""


def _is_foreign_institution(profile: UserProfile, rules: dict) -> bool:
    inst = _institution_name(profile)
    if any(kw in inst for kw in rules["local_institution_keywords"]):
        return False
    return profile.country != "SG"


def _institution_is_english_medium(profile: UserProfile, rules: dict) -> bool:
    """True when the institution on record is known to teach in English.

    An absent keyword list degrades to False, i.e. to "unconfirmed" — we ask the
    applicant to confirm rather than granting a waiver we cannot justify.
    """
    inst = _institution_name(profile)
    if not inst:
        return False
    return any(kw in inst for kw in rules.get(_ENGLISH_MEDIUM_KEYWORDS_FIELD, ()))


def _english_proof_unconfirmed(profile: UserProfile, rules: dict) -> bool:
    """True when the TOEFL/IELTS requirement can neither be ruled out nor asserted.

    UserProfile has no `medium_of_instruction` field, so the requirement can only
    ever be ruled OUT, from a positive signal:
      1. the institution on record is a known English-medium institution, or
      2. failing that, the applicant's education system is on
         `english_exempt_countries` (a coarse proxy, used only to waive).
    With no positive signal the answer is "unconfirmed": the rule surfaces the
    item so the applicant can confirm, but declares `required: false`, so it is
    never counted as an outstanding blocking requirement. Nationality can
    therefore only waive the requirement, never impose it.
    """
    if _institution_is_english_medium(profile, rules):
        return False
    return profile.country not in rules["english_exempt_countries"]


def _classification_below(profile: UserProfile, threshold: str) -> bool:
    """True if the applicant's honours class is strictly worse than `threshold`.

    Unknown / missing classification is treated as NOT below (don't over-trigger
    extra requirements on incomplete data — surface via clarification instead).
    """
    ab = profile.academic_background
    cls = ab.degree_classification if ab else None
    if cls is None:
        return False
    # `unknown` is not in _CLASSIFICATION_ORDER, so the next guard covers it too.
    if cls.value not in _CLASSIFICATION_ORDER or threshold not in _CLASSIFICATION_ORDER:
        return False
    return _CLASSIFICATION_ORDER.index(cls.value) > _CLASSIFICATION_ORDER.index(threshold)


# Every condition an authored rule may reference. Must stay in step with
# admin/schemas.py::SUPPORTED_CONDITIONS, otherwise a rule can pass authoring
# validation and then escalate at runtime as an unknown condition.
# `english_proof_required: true` means "the medium of instruction is not
# confirmed English", i.e. the item is surfaced for confirmation.
_CONDITION_EVALUATORS: dict[str, Callable[[UserProfile, dict, object], bool]] = {
    "foreign_institution":
        lambda p, r, v: _is_foreign_institution(p, r) == v,
    "english_proof_required":
        lambda p, r, v: _english_proof_unconfirmed(p, r) == v,
    "application_type":
        lambda p, r, v: p.application_type is not None and p.application_type.value == v,
    "degree_classification_below":
        lambda p, r, v: _classification_below(p, str(v)),
}


def _condition_holds(cond_key: str, cond_val, profile: UserProfile, rules: dict) -> bool:
    evaluator = _CONDITION_EVALUATORS.get(cond_key)
    if evaluator is None:
        raise _UnknownCondition(cond_key)
    return evaluator(profile, rules, cond_val)


def _spec_applies(spec: dict, profile: UserProfile, rules: dict) -> bool:
    """AND over every condition declared on a conditional item."""
    return all(
        _condition_holds(cond_key, cond_val, profile, rules)
        for cond_key, cond_val in spec["applies_when"].items()
    )


def _requirement_level(spec: dict) -> str:
    """Read an item's requirement level, rejecting anything the engine cannot map.

    admin/schemas.py::RequirementLevel already rejects a bad level at authoring
    time, but the rules file is plain JSON on disk and is loaded here without
    going through that schema, so a hand edit can still reach this point. It
    raises instead of guessing: guessing "required" would re-impose a requirement
    we cannot justify, and guessing "not required" would silently drop a
    mandatory document.
    """
    level = spec.get("requirement")
    if level not in _REQUIREMENT_LEVELS:
        raise ValueError(
            f"item {spec.get('key')!r} declares unknown requirement level {level!r}; "
            f"expected one of {list(_REQUIREMENT_LEVELS)}"
        )
    return level


def _doc_status(key: str, profile: UserProfile) -> str:
    """Resolve a document's status: rich document_status > submitted list > missing."""
    app = profile.application
    if app is None:
        return "missing"
    if key in app.document_status:
        return app.document_status[key].value
    return "submitted" if key in app.submitted_documents else "missing"


def urgency_for(days_left: int) -> str:
    """Urgency bucket for a deadline `days_left` days away (negative == past due)."""
    if days_left < 0:
        return "overdue"
    if days_left <= _URGENT_WITHIN_DAYS:
        return "urgent"
    if days_left <= _SOON_WITHIN_DAYS:
        return "soon"
    return "info"


def _document_deadline(profile: UserProfile) -> str | None:
    """The date this profile's documents are due, or None if none is on record."""
    if profile.application is None:
        return None
    deadlines = profile.application.deadlines
    for key in _DOCUMENT_DEADLINE_KEYS:
        iso = deadlines.get(key)
        if iso:
            return iso
    return None


def _deadline_and_urgency(status: str, profile: UserProfile,
                          today: date) -> tuple[str | None, str | None]:
    iso = _document_deadline(profile)
    if not iso:
        return None, None
    # Urgency only matters while the item is still outstanding.
    if status not in OUTSTANDING_STATUSES:
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
        deadline, urgency = _deadline_and_urgency(status, profile, today)
        item = ChecklistItem(
            key=spec["key"], label=spec["label"], requirement=_requirement_level(spec),
            status=status, why=spec["why"], deadline=deadline,
        )
        if item.required:
            item.urgency = urgency  # we only chase what we actually require
        items.append(item)

    for spec in rules["base_items"]:
        add(spec)

    for spec in rules["conditional_items"]:
        try:
            if _spec_applies(spec, profile, rules):
                add(spec)
        except _UnknownCondition as e:
            unknown = str(e)

    missing = sum(1 for it in items if it.status == "missing")
    outstanding = sum(1 for it in items if it.required and it.status in OUTSTANDING_STATUSES)
    return ChecklistResult(
        items=items, missing_count=missing, outstanding_count=outstanding,
        unknown_condition=unknown,
    )
