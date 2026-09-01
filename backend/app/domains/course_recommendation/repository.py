"""
Course-recommendation data access — parses the knowledge base's document
chunks into the structured models the rule engine works on.

This module deliberately does not open its own database connection: it
reads through the shared knowledge_db adapter (which caches the full
corpus in process), so the only "repository work" here is deterministic
parsing of chunk content/metadata into typed models. If a chunk cannot be
parsed, it is skipped with a printed warning rather than silently
mis-parsed — the corpus is small and regular, so a parse failure means the
upstream chunking format changed and should be surfaced.

Read-only: never writes to any database.
"""

from __future__ import annotations

import re

from app.adapters.knowledge_db_adapter import knowledge_db
from app.domains.course_recommendation.models import CareerRole, Course, CurriculumRule

# "FT5005 Machine Learning for Finance (4 units)." — the fixed header every
# courses chunk starts with.
_COURSE_HEADER = re.compile(r"^(?P<code>[A-Z]{2,4}\d{4}[A-Z]?)\s+(?P<title>.+?)\s+\((?P<units>\d+)\s+units?\)\.")

# The labelled trailing segments a courses chunk may carry, in any order.
_SEGMENT_SPLIT = re.compile(r"(Prerequisite:|Preclusion:|Skills covered:)")

# Every chunk's un-labelled lead segment is actually
# "<header>. Faculty: <faculty>. Description: <the real description>" (see
# _split_segments) — this strips everything up to and including the
# "Description:" label so Course.description holds just the description,
# not a second copy of the code/title/faculty already shown elsewhere.
_DESCRIPTION_LABEL = re.compile(r"^.*?\bDescription:\s*", re.DOTALL)

# Display label used inside "Skills covered: ..." → canonical skill id used
# by career_roles.metadata.required_skills. Both vocabularies come from the
# same upstream chunking source, so this mapping is exhaustive.
SKILL_LABEL_TO_ID = {
    "AI / Machine Learning": "ai_ml",
    "Compliance / regulation": "regulation",
    "Data analytics": "data_analytics",
    "Finance knowledge": "finance",
    "Payments / blockchain / trading systems": "payments_systems",
    "Product / business understanding": "product",
    "Programming": "programming",
    "Risk modelling": "risk_modeling",
    "Security and resilience": "security",
}

_courses_cache: list[Course] | None = None
_roles_cache: dict[str, CareerRole] | None = None
_rules_cache: list[CurriculumRule] | None = None


def _split_segments(content: str) -> dict[str, str]:
    """Splits a courses chunk into its labelled parts. The part before the
    first label is returned under "" (header + description)."""
    parts = _SEGMENT_SPLIT.split(content)
    segments = {"": parts[0].strip()}
    for label, body in zip(parts[1::2], parts[2::2], strict=True):
        segments[label] = body.strip()
    return segments


def _parse_skills(skills_text: str) -> tuple[str, ...]:
    """"AI / Machine Learning (machine learning, ...); Data analytics (...)"
    → ("ai_ml", "data_analytics"). Unknown labels are skipped with a warning
    (means the upstream skill vocabulary changed)."""
    ids = []
    for part in skills_text.split(";"):
        label = part.split("(")[0].strip().rstrip(".")
        if not label:
            continue
        skill_id = SKILL_LABEL_TO_ID.get(label)
        if skill_id is None:
            print(f"[course_recommendation.repository] Warning: unknown skill label {label!r}")
            continue
        ids.append(skill_id)
    return tuple(ids)


def _parse_course(chunk: dict) -> Course | None:
    header_match = _COURSE_HEADER.match(chunk["content"])
    if not header_match:
        print(f"[course_recommendation.repository] Warning: unparseable course chunk {chunk['chunk_key']!r}")
        return None

    segments = _split_segments(chunk["content"])
    md = chunk["metadata"] or {}
    return Course(
        code=header_match["code"],
        title=header_match["title"],
        units=int(header_match["units"]),
        section=md.get("annex_section", ""),
        skills=_parse_skills(segments.get("Skills covered:", "")),
        description=_DESCRIPTION_LABEL.sub("", segments[""], count=1),
        prerequisite_text=segments.get("Prerequisite:", ""),
        preclusion_text=segments.get("Preclusion:", ""),
        can_recommend=bool(md.get("can_recommend", False)),
        source_url=md.get("source_url", ""),
    )


def load_courses() -> list[Course]:
    """All catalogue courses (including referenced-only ones — the rule
    engine needs those to recognise completed courses and preclusions, even
    though it only ever recommends can_recommend=True ones)."""
    global _courses_cache
    if _courses_cache is None:
        parsed = (_parse_course(c) for c in knowledge_db.fetch_all_chunks() if c["source_table"] == "courses")
        _courses_cache = [c for c in parsed if c is not None]
    return _courses_cache


def load_career_roles() -> dict[str, CareerRole]:
    """role_id → CareerRole, from career_roles chunk metadata (clean and
    structured — no content parsing needed)."""
    global _roles_cache
    if _roles_cache is None:
        _roles_cache = {}
        for chunk in knowledge_db.fetch_all_chunks():
            if chunk["source_table"] != "career_roles":
                continue
            md = chunk["metadata"] or {}
            role_id = md.get("role_id")
            if not role_id:
                print(f"[course_recommendation.repository] Warning: career_roles chunk {chunk['chunk_key']!r} has no role_id")
                continue
            _roles_cache[role_id] = CareerRole(
                role_id=role_id,
                role_title=md.get("role_title", role_id),
                required_skills=tuple(md.get("required_skills", [])),
            )
    return _roles_cache


def load_curriculum_rules() -> list[CurriculumRule]:
    """All Annex A curriculum rules, every intake. Callers filter by intake
    (see service.py)."""
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = []
        for chunk in knowledge_db.fetch_all_chunks():
            if chunk["source_table"] != "course_rules":
                continue
            md = chunk["metadata"] or {}
            _rules_cache.append(CurriculumRule(
                rule_key=chunk["chunk_key"],
                category=md.get("category", ""),
                intake=md.get("intake", ""),
                text=chunk["content"],
            ))
    return _rules_cache
