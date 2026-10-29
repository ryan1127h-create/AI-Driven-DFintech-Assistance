"""
S2 — gathers everything one turn's report needs. The only module in this
tool that reads the profile or the knowledge base.

The reads don't depend on one another and are I/O-bound, so they run in
parallel. Their failure policies differ:

  - profile facts and lifecycle stage: fail open — the answer runs
    unpersonalised (as it does without consent) and the reply says so;
  - readiness gaps: fail open — they only add to the roadmap;
  - knowledge base (role families, course tags, courses): fail closed —
    without the role catalogue there is nothing to plan against, so the
    error propagates to the tool's fallback reply.

role_catalog() is also read on its own, first, for S1's parser; the
knowledge base caches it, so the second read is free.
"""

from __future__ import annotations

import concurrent.futures

from app.core.logging import get_logger
from app.tools import certifications
from app.domains.knowledge_retrieval.interface import list_course_tags, list_courses, list_role_tags
from app.domains.profile.interface import (
    derived_readiness_gaps,
    describe_value,
    field_labels,
    get_profile_field,
    get_profile_for_purpose,
    missing_purpose_consent,
)
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched

logger = get_logger(__name__)

_READ_TIMEOUT_SECONDS = 10.0

_CONSENT_OFF_NOTE = (
    "Personalised recommendations are turned off, so this doesn't use your profile. Turning them on in "
    "Settings lets the advice be based on your own skills and plans."
)
_PROFILE_UNAVAILABLE_NOTE = "Your profile couldn't be read just now, so this advice isn't personalised."


def role_catalog() -> list[dict]:
    """[{tag, name, name_zh, definition, required_skills}] for every role
    family that names its skills (name_zh lets S1 match a role named in
    Chinese)."""
    return [
        {"tag": r["tag"], "name": r["name_en"], "name_zh": r.get("name_zh") or "",
         "definition": r.get("definition") or "", "required_skills": list(r["required_skills"])}
        for r in list_role_tags() if r.get("required_skills")
    ]


def _course_links() -> list[dict]:
    """Courses on offer and their role tags: only an active course counts
    as the programme's support for a role."""
    titles = {row["course_code"]: row["title"] for row in list_courses() if row.get("can_recommend")}
    return [
        {"code": code, "title": titles[code], "tags": tags}
        for code, tags in list_course_tags().items() if code in titles
    ]


def _raw_values(value) -> list:
    items = value if isinstance(value, list) else [value]
    return [item.get("key") if isinstance(item, dict) else item for item in items]


def _certification_labels(items) -> dict:
    """The evidence key of each certification -> its label with the level."""
    return {
        str(certifications.evidence_key(item)): certifications.evidence_label(
            item, describe_value("certifications", item.get("key") if isinstance(item, dict) else item))
        for item in (items if isinstance(items, list) else [items]) if item
    }


def evidence_labels(facts: dict) -> dict:
    """How each fact on file (and each of its values) is shown in the reply."""
    labels = field_labels(facts)
    shown = {
        key: {"label": labels.get(key, key),
              "values": {str(v): describe_value(key, v) for v in _raw_values(value) if v is not None}}
        for key, value in facts.items() if value not in (None, "", [])
    }
    if "certifications" in shown:
        shown["certifications"]["values"] = _certification_labels(facts["certifications"])
    return shown


def _result(future, default, what: str, notes: list[str], note: str | None = None):
    if future is None:
        return default
    try:
        return future.result(timeout=_READ_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("career planning: reading %s failed", what)
        if note:
            notes.append(note)
        return default


def prefetch(user_id: str | None) -> Prefetched:
    notes: list[str] = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        catalog = pool.submit(role_catalog)
        links = pool.submit(_course_links)
        facts = pool.submit(get_profile_for_purpose, user_id, "career") if user_id else None
        stage = pool.submit(get_profile_field, user_id, "lifecycle_stage") if user_id else None
        gaps = pool.submit(derived_readiness_gaps, user_id) if user_id else None
        consent = pool.submit(missing_purpose_consent, user_id, "career") if user_id else None

        facts_value = _result(facts, None, "the profile", notes, _PROFILE_UNAVAILABLE_NOTE)
        stage_value = _result(stage, None, "the lifecycle stage", notes)
        gaps_value = _result(gaps, [], "readiness gaps", notes)
        consent_missing = _result(consent, "unknown", "consent", notes)
        if consent_missing and consent_missing != "unknown":
            notes.append(_CONSENT_OFF_NOTE)
        catalog_value = catalog.result(timeout=_READ_TIMEOUT_SECONDS)
        links_value = links.result(timeout=_READ_TIMEOUT_SECONDS)
    finally:
        pool.shutdown(wait=False)

    try:
        labels = evidence_labels(facts_value or {})
    except Exception:
        logger.exception("career planning: labelling the profile facts failed, showing raw values")
        labels = {}
    return Prefetched(
        evidence_labels=labels,
        facts=facts_value or {},
        stage=stage_value,
        readiness_gaps=gaps_value,
        role_catalog=catalog_value,
        course_links=links_value,
        notes=tuple(dict.fromkeys(notes)),
        profile_read=bool(user_id) and facts_value is not None and consent_missing is None,
    )
