"""Internal domain models for the career_planning module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CareerPlanResult:
    """What service.create_career_plan() returns to api.py / interface.py."""
    target_role: str | None
    current_fit: str
    skill_gaps: tuple[str, ...]
    recommended_courses: tuple[dict, ...]
    short_term_actions: tuple[str, ...]
    medium_term_actions: tuple[str, ...]
    notes: tuple[str, ...]
    sources: tuple[str, ...]
