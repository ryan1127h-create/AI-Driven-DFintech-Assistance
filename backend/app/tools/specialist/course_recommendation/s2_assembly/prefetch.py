"""
S2 — gathers everything one turn's report needs. The only module in this
tool that reads the profile or the knowledge base.

The three reads (profile facts, derived readiness/graduation notes, the
knowledge-base catalogue) don't depend on one another and are I/O-bound,
so they run in parallel. Their failure policies differ:

  - profile facts: fail open — the recommendation runs unpersonalised (as
    it does without consent) and the reply says so;
  - derived notes: fail open — they only add notes;
  - knowledge base: fail closed — without the catalogue there is nothing
    to recommend, so the error propagates to the tool's fallback reply.

The role is resolved here too: the role named in the message (if it is a
known role tag), else the profile's main role, else its first listed role.
"""

from __future__ import annotations

import concurrent.futures

from app.core.logging import get_logger
from app.domains.knowledge_retrieval.interface import (
    get_role_profile,
    list_course_electives,
    list_course_tags,
    list_courses,
    list_curriculum_rules,
    list_role_tags,
    match_role_tag,
)
from app.domains.profile.interface import derived_course_notes, describe_value, get_profile_for_purpose
from app.tools.specialist.course_recommendation.s2_assembly.prefetched import LABELLED_FIELDS, Prefetched

logger = get_logger(__name__)

# Per-read limit; the tool's own timeout bounds the whole turn.
_READ_TIMEOUT_SECONDS = 10.0

_PROFILE_UNAVAILABLE_NOTE = (
    "Your profile couldn't be read just now, so this recommendation isn't personalised."
)


def resolve_role_tag(facts: dict, target_role_hint: str | None) -> str | None:
    if target_role_hint:
        tag = match_role_tag(target_role_hint)
        if tag:
            return tag
    families = facts.get("target_role_families") or []
    return facts.get("main_target_role") or (families[0] if families else None)


def _knowledge() -> dict:
    return {
        "courses": list_courses(),
        "curriculum_rules": list_curriculum_rules(),
        "course_tags": list_course_tags(),
        "role_tags": list_role_tags(),
        "course_electives": list_course_electives(),
    }


def prefetch(user_id: str | None, target_role_hint: str | None) -> Prefetched:
    notes: list[str] = []
    # Not a context manager: leaving the `with` block would wait for a read
    # that has already timed out.
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    try:
        knowledge = pool.submit(_knowledge)
        facts_future = pool.submit(get_profile_for_purpose, user_id, "course") if user_id else None
        derived_future = pool.submit(derived_course_notes, user_id) if user_id else None

        facts: dict = {}
        if facts_future is not None:
            try:
                facts = facts_future.result(timeout=_READ_TIMEOUT_SECONDS)
            except Exception:
                logger.exception("course recommendation: reading the profile failed, not personalising")
                notes.append(_PROFILE_UNAVAILABLE_NOTE)

        derived = {"readiness": [], "graduation": []}
        if derived_future is not None:
            try:
                derived = derived_future.result(timeout=_READ_TIMEOUT_SECONDS)
            except Exception:
                logger.exception("course recommendation: reading derived notes failed, leaving them out")

        kb = knowledge.result(timeout=_READ_TIMEOUT_SECONDS)
    finally:
        pool.shutdown(wait=False)

    role_tag = resolve_role_tag(facts, target_role_hint)
    return Prefetched(
        facts=facts,
        fact_labels={key: describe_value(key, facts[key]) for key in LABELLED_FIELDS if key in facts},
        role_labels={
            tag: describe_value("target_role_families", tag)
            for tag in facts.get("target_role_families") or []
        },
        readiness_notes=tuple(derived["readiness"]),
        graduation_notes=tuple(derived["graduation"]),
        role_tag=role_tag,
        role_profile=get_role_profile(role_tag) if role_tag else None,
        notes=tuple(notes),
        **kb,
    )
