"""
explore — the catalogue programmes that meet the stated conditions
(country, study mode, kind of programme), in catalogue order, with MSc DFT
alongside as the baseline. A filter, never a ranking: matches are listed,
not ordered by any notion of fit. A programme whose study modes aren't on
file is left out of a study-mode filter rather than assumed to match.
"""

from __future__ import annotations

from app.domains.specialist.program_comparison.models import Conditions, ProgramView
from app.domains.specialist.program_comparison.stages.s6_modes.base import program_result


def _meets(view: ProgramView, c: Conditions) -> bool:
    if c.countries and view.country_code not in c.countries:
        return False
    if c.categories and view.category not in c.categories:
        return False
    if c.study_mode and c.study_mode not in (view.raw_facts.get("study_modes") or ()):
        return False
    return True


class Explore:
    def assemble(self, views, fits, *, target_id, subject_ids, dimensions, conditions: Conditions):
        matches = tuple(
            program_result(view, fits.get(pid), dimensions)
            for pid, view in views.items()
            if pid != target_id and _meets(view, conditions)
        )
        return program_result(views[target_id], fits.get(target_id), dimensions), (), matches, ()
