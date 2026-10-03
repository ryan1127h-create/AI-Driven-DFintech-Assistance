"""
Public interface of the profile domain — the only module other domains
(and the orchestrator) are allowed to import from app.domains.profile.
Everything else in this package (repository, validation, service
internals) is private.

Current consumers:
    - chatbot uses get_profile_summary_text() to inject the user's profile
      into the conversation.
    - auth uses set_lifecycle_stage() and record_consents() at
      registration, and get_profile_field() to derive the user's role.
    - checklist uses set_lifecycle_stage() when an application is bound.
    - the specialist chat tools read get_profile_for_purpose() — course
      recommendation ("course"), career planning ("career"), programme
      comparison ("adm") — and render facts with describe_value() /
      describe_facts() for the specialists they call.
    - cv_import checks the CV-processing consent, asks which fields a CV
      may fill (cv_targets) and how each value would be stored
      (check_value), and records each upload and its extracted
      candidates (start/fail/finish_cv_document, latest_cv_import), and
      forgets them on request (delete_cv_data).
    - derived_labels reads the profile (get_profile_values,
      field_definitions) and stores what it computes (save_derived_labels);
      the course recommendation tool reads derived_course_notes(), which the
      chat summary includes too.

Usage:
    from app.domains.profile.interface import get_profile_summary_text
"""

from __future__ import annotations

from app.domains.profile import service

__all__ = [
    "check_value",
    "derived_course_notes",
    "cv_targets",
    "describe_facts",
    "delete_cv_data",
    "describe_value",
    "get_profile_field",
    "get_profile_for_purpose",
    "fail_cv_document",
    "field_definitions",
    "get_derived_labels",
    "get_profile_values",
    "finish_cv_document",
    "get_profile_summary_text",
    "has_consent",
    "latest_cv_import",
    "list_user_ids",
    "record_consents",
    "save_derived_labels",
    "set_lifecycle_stage",
    "start_cv_document",
]


def get_profile_for_purpose(user_id: str, purpose: str) -> dict:
    """{field_key: value} usable for one purpose under the user's consents
    (empty without consent); see service.get_facts_for_purpose."""
    return service.get_facts_for_purpose(user_id, purpose)


def describe_facts(facts: dict) -> list[str]:
    """One English "Label: value" line per fact, in field-dictionary order."""
    return service.describe_facts(facts)


def describe_value(field_key: str, value) -> str:
    """English display text for a field value."""
    return service.describe_value(field_key, value)


def get_profile_field(user_id: str, field_key: str):
    """The current merged value of one field (see v_profile), or None."""
    return service.get_field(user_id, field_key)


def set_lifecycle_stage(user_id: str, stage: str, *, source: str, actor: str) -> None:
    """Moves the user to a lifecycle stage; see service.set_lifecycle_stage."""
    service.set_lifecycle_stage(user_id, stage, source=source, actor=actor)


def record_consents(user_id: str, decisions: dict[str, bool]) -> None:
    """Records consent decisions (e.g. those made at registration)."""
    service.update_consents(user_id, decisions)


def get_profile_summary_text(user_id: str) -> str:
    """The consent-filtered profile summary for the chat prompt; empty
    string if there is nothing to inject (caller should then skip the
    SystemMessage entirely)."""
    return service.chat_summary_text(user_id)


def has_consent(user_id: str, consent_key: str) -> bool:
    return service.has_consent(user_id, consent_key)


def cv_targets(user_id: str) -> list[dict]:
    """The field definitions a CV may pre-fill for this user."""
    return service.cv_targets(user_id)


def check_value(field_key: str, value):
    """The value normalized as the profile would store it, or None."""
    return service.check_value(field_key, value)


def start_cv_document(user_id: str) -> str:
    return service.start_cv_document(user_id)


def fail_cv_document(document_id: str, error: str) -> None:
    service.fail_cv_document(document_id, error)


def finish_cv_document(user_id: str, document_id: str, candidates: dict) -> dict:
    """candidates: {field_key: {value, quote}}, already checked."""
    return service.finish_cv_document(user_id, document_id, candidates)


def latest_cv_import(user_id: str) -> dict | None:
    return service.latest_cv_import(user_id)


def delete_cv_data(user_id: str) -> int:
    """Clears kept CV candidates and quotes; profile values stay."""
    return service.delete_cv_data(user_id)


def field_definitions() -> dict:
    """The whole field dictionary, {field_key: definition}."""
    return service.repository.load_field_definitions()


def get_profile_values(user_id: str) -> dict:
    """Unfiltered {field_key: value}; for derived-label rules only."""
    return service.get_profile_values(user_id)


def save_derived_labels(user_id: str, labels: dict, rules_version: str) -> None:
    service.save_derived_labels(user_id, labels, rules_version)


def get_derived_labels(user_id: str) -> dict | None:
    return service.get_derived_labels(user_id)


def list_user_ids() -> list[str]:
    return service.list_user_ids()


def derived_course_notes(user_id: str) -> dict[str, list[str]]:
    """{"readiness": [...], "graduation": [...]} sentences (consent-gated)."""
    return service.derived_course_notes(user_id)
