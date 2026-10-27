"""
Public interface of the knowledge_retrieval domain — the only module other
domains are allowed to import from app.domains.knowledge_retrieval.

Current consumers:
    - career_planning retrieves career-track reference text
      (filter_topics={"career"}) for its plan narrative.
    - app/tools/specialist/course_recommendation/s2_assembly/ uses
      list_courses()/list_curriculum_rules()/list_course_electives()/
      list_course_tags()/list_role_tags()/get_role_profile()/
      match_role_tag() to assemble the report course_recommendation's own
      interface.py needs — that domain still never reads this one itself;
      the chat adapter builds the report before handing it over.
    - checklist labels an application's documents and explains its status
      with list_admissions_items() / explain_application_status().
    - profile reads the role tags (list_role_tags()) for validation and
      display names.
    - admin rebuilds an edited row's retrieval chunk with chunk_builder and
      embed_for_retrieval(), then calls reload_catalogue().

Usage:
    from app.domains.knowledge_retrieval.interface import retrieve, cited_sources
"""

from __future__ import annotations

from app.domains.knowledge_retrieval import chunk_builder
from app.domains.knowledge_retrieval.models import Hit
from app.domains.knowledge_retrieval.service import (
    build_context,
    cited_sources,
    embed_for_retrieval,
    explain_application_status,
    get_role_profile,
    list_admissions_items,
    list_course_electives,
    list_course_schedule,
    list_course_tags,
    list_courses,
    list_curriculum_rules,
    list_role_tags,
    match_role_tag,
    reload_catalogue,
    retrieve,
    warm_cache,
)

__all__ = [
    "Hit",
    "chunk_builder",
    "embed_for_retrieval",
    "retrieve",
    "build_context",
    "cited_sources",
    "list_admissions_items",
    "explain_application_status",
    "list_courses",
    "list_curriculum_rules",
    "list_course_electives",
    "list_course_schedule",
    "list_course_tags",
    "list_role_tags",
    "get_role_profile",
    "match_role_tag",
    "reload_catalogue",
    "warm_cache",
]
