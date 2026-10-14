"""What every mode shares: one programme's result restricted to the
aspects being answered."""

from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from app.domains.specialist.program_comparison.models import (
    ApplicantFit,
    Conditions,
    Contrast,
    ProgramView,
)


def program_result(view: ProgramView, fit: ApplicantFit | None, dimensions: tuple[str, ...]) -> dict:
    sources = [url for d in dimensions for url in view.sources.get(d, ())]
    return {
        "program_id": view.program_id, "name": view.name, "short_name": view.short_name,
        "university": view.university, "university_short": view.university_short,
        "city": view.city, "country": view.country, "category": view.category, "is_target": view.is_target,
        "intake_year": view.intake_year, "official_url": view.official_url, "summary": view.summary,
        "facts": {d: view.facts[d] for d in dimensions if d in view.facts},
        "fit": {d: fit.by_dimension[d] for d in dimensions if fit and d in fit.by_dimension},
        "conflicts": [asdict(c) for c in view.conflicts if c.dimension in dimensions],
        "sources": list(dict.fromkeys([*sources, view.official_url])),
        "intake_mismatch": bool(fit and fit.intake_mismatch),
    }


class ModeStrategy(Protocol):
    def assemble(
        self,
        views: dict[str, ProgramView],
        fits: dict[str, ApplicantFit],
        *,
        target_id: str,
        subject_ids: tuple[str, ...],
        dimensions: tuple[str, ...],
        conditions: Conditions,
    ) -> tuple[dict | None, tuple[dict, ...], tuple[dict, ...], tuple[Contrast, ...]]:
        """(baseline, subjects, matches, contrasts)."""
        ...
