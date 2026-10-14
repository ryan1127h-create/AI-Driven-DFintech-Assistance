"""
S2 — gathers everything one turn's report needs. The only module in this
tool that reads the catalogue, the profile or the knowledge base.

The reads don't depend on one another and are I/O-bound, so they run in
parallel. Their failure policies differ:

  - programme catalogue: fail closed — without it there is nothing to
    compare, so the error propagates to the tool's fallback reply;
  - profile facts (admissions and career purposes): fail open — the
    answer runs unpersonalised (as it does without consent) and says so;
  - role families: fail open — only the curriculum's fit to a target role
    is lost.

catalogue() and role_catalog() are also read on their own, first, for
S1's parser; both are cached where they are read, so the second read is
free.
"""

from __future__ import annotations

import concurrent.futures

from app.core.logging import get_logger
from app.domains.knowledge_retrieval.interface import list_role_tags
from app.domains.profile.interface import get_profile_for_purpose, missing_purpose_consent
from app.domains.program_catalog.interface import list_programs
from app.tools.specialist.program_comparison.s2_assembly.prefetched import Prefetched

logger = get_logger(__name__)

_READ_TIMEOUT_SECONDS = 10.0
_ROLE_FIELDS = ("main_target_role", "target_role_families")

_CONSENT_OFF_NOTE = (
    "Personalised recommendations are turned off, so this compares the programmes' published facts without "
    "using your profile. Turning them on in Settings lets it relate each programme to your own situation."
)
_PROFILE_UNAVAILABLE_NOTE = "Your profile couldn't be read just now, so this comparison isn't personalised."


def catalogue() -> list[dict]:
    return list_programs()


def role_catalog() -> list[dict]:
    """[{tag, name, name_zh, required_skills}] for every role family that
    names its skills."""
    return [
        {"tag": r["tag"], "name": r["name_en"], "name_zh": r.get("name_zh") or "",
         "required_skills": list(r["required_skills"])}
        for r in list_role_tags() if r.get("required_skills")
    ]


def _result(future, default, what: str, notes: list[str], note: str | None = None):
    if future is None:
        return default
    try:
        return future.result(timeout=_READ_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("programme comparison: reading %s failed", what)
        if note:
            notes.append(note)
        return default


def prefetch(user_id: str | None) -> Prefetched:
    notes: list[str] = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    try:
        programs = pool.submit(catalogue)
        roles = pool.submit(role_catalog)
        facts = pool.submit(get_profile_for_purpose, user_id, "adm") if user_id else None
        career = pool.submit(get_profile_for_purpose, user_id, "career") if user_id else None
        consent = pool.submit(missing_purpose_consent, user_id, "adm") if user_id else None

        facts_value = _result(facts, {}, "the admissions profile", notes, _PROFILE_UNAVAILABLE_NOTE)
        career_value = _result(career, {}, "the career profile", notes)
        if _result(consent, None, "consent", notes):
            notes.append(_CONSENT_OFF_NOTE)
        roles_value = _result(roles, [], "role families", notes)
        programs_value = programs.result(timeout=_READ_TIMEOUT_SECONDS)
    finally:
        pool.shutdown(wait=False)

    return Prefetched(
        programs=programs_value,
        facts=facts_value,
        role_facts={k: career_value.get(k) for k in _ROLE_FIELDS if career_value.get(k)},
        role_catalog=roles_value,
        notes=tuple(dict.fromkeys(notes)),
    )
