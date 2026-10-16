"""
S2 — the assessment's one data-gathering step: the applicant's profile
facts (the admissions and career purposes, which share one consent) with
where each came from, and MSc DFT's checked record in the programme
catalogue, read in parallel.

Failure handling:
  - the profile and the consent fail open — the assessment runs on the
    message alone and the reply says so;
  - the programme catalogue fails open too: the builder then has no
    requirements to check against and the tool says the assessment is
    unavailable rather than guess them.
"""

from __future__ import annotations

import concurrent.futures
from datetime import date

from app.core.logging import get_logger
from app.domains.profile.interface import (
    field_definitions,
    get_fact_sources_for_purpose,
    get_profile_for_purpose,
    missing_purpose_consent,
)
from app.domains.program_catalog import interface as program_catalog
from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched

logger = get_logger(__name__)

_READ_TIMEOUT_SECONDS = 10.0
# The purposes the assessed fields belong to; both use the same consent.
PURPOSES = ("adm", "career")

PROFILE_UNAVAILABLE_NOTE = "Your profile couldn't be read just now, so this assessment uses only your message."
CONSENT_OFF_NOTE = ("Personalised recommendations are turned off, so this assessment uses only what your message "
                    "says, not your profile.")


def _profile(user_id: str) -> tuple[dict, dict]:
    facts, sources = {}, {}
    for purpose in PURPOSES:
        facts.update(get_profile_for_purpose(user_id, purpose))
        sources.update(get_fact_sources_for_purpose(user_id, purpose))
    return facts, sources


# The fields whose values a reply names (the domain's findings carry them raw).
_LABELLED_FIELDS = ("degree_discipline_category", "highest_degree", "gpa_band", "tech_stack", "prior_coursework",
                    "total_work_years", "function_experience", "research_output", "certifications")


def value_labels() -> dict[str, str]:
    """{raw value: display label} for the assessed fields; {} when the
    dictionary can't be read (raw values then show)."""
    try:
        definitions = field_definitions()
    except Exception:
        logger.exception("assessment: reading the field dictionary failed")
        return {}
    labels: dict[str, str] = {}
    for key in _LABELLED_FIELDS:
        labels.update({str(k): v for k, v in ((definitions.get(key) or {}).get("value_labels") or {}).items()})
    return labels


def _programme() -> dict | None:
    return next((p for p in program_catalog.list_programs() if p["is_target"]), None)


def prefetch(user_id: str | None, today: date | None = None) -> Prefetched:
    today = today or date.today()
    notes: list[str] = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    try:
        programme_f = pool.submit(_programme)
        profile_f = pool.submit(_profile, user_id) if user_id else None
        consent_f = pool.submit(missing_purpose_consent, user_id, "adm") if user_id else None

        try:
            programme = programme_f.result(timeout=_READ_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("assessment: reading the programme catalogue failed")
            programme = None
        facts = sources = None
        if profile_f is not None:
            try:
                facts, sources = profile_f.result(timeout=_READ_TIMEOUT_SECONDS)
            except Exception:
                logger.exception("assessment: reading the profile failed")
                notes.append(PROFILE_UNAVAILABLE_NOTE)
        consent_missing = "unknown"
        if consent_f is not None:
            try:
                consent_missing = consent_f.result(timeout=_READ_TIMEOUT_SECONDS)
            except Exception:
                logger.exception("assessment: reading the consent failed")
        if consent_missing and consent_missing != "unknown":
            notes.append(CONSENT_OFF_NOTE)
    finally:
        pool.shutdown(wait=False)

    return Prefetched(
        facts=facts or {},
        fact_sources=sources or {},
        programme=programme,
        today=today,
        profile_read=bool(user_id) and facts is not None and consent_missing is None,
        consent_missing=consent_missing if consent_missing not in (None, "unknown") else None,
        notes=tuple(dict.fromkeys(notes)),
        value_labels=value_labels(),
    )
