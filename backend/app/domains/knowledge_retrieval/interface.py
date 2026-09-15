"""
Public interface of the knowledge_retrieval domain — the only module other
domains are allowed to import from app.domains.knowledge_retrieval.

Current consumers:
    - career_planning retrieves career-track reference text
      (filter_topics={"career"}) for its plan narrative.
    - knowledge_qa and assessment both cite ADMISSIONS_OFFICIAL_SOURCES in
      their own prompts.
    - app/tools/specialist/course_recommendation_tool.py uses
      list_courses()/list_curriculum_rules()/resolve_role_profile()/
      list_module_skills()/list_career_role_modules()/list_course_electives()
      to assemble the report course_recommendation's own interface.py
      needs — that domain still never reads this one itself; the chat
      adapter builds the report before handing it over.

Usage:
    from app.domains.knowledge_retrieval.interface import retrieve, cited_sources
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.models import Hit
from app.domains.knowledge_retrieval.service import (
    ADMISSIONS_OFFICIAL_SOURCES,
    build_context,
    cited_sources,
    list_courses,
    list_course_electives,
    list_curriculum_rules,
    list_career_role_modules,
    list_module_skills,
    resolve_role_profile,
    retrieve,
)

__all__ = [
    "Hit",
    "retrieve",
    "build_context",
    "cited_sources",
    "ADMISSIONS_OFFICIAL_SOURCES",
    "list_courses",
    "list_curriculum_rules",
    "resolve_role_profile",
    "list_module_skills",
    "list_career_role_modules",
    "list_course_electives",
]
