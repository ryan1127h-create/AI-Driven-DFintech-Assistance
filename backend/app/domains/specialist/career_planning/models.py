"""Internal domain models for independent career planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CareerPlanResult:
    target_role: str
    current_fit: str
    skill_assessment: tuple[dict, ...]
    phases: tuple[dict, ...]
    success_indicators: tuple[str, ...]
    notes: tuple[str, ...]
    sources: tuple[str, ...]
