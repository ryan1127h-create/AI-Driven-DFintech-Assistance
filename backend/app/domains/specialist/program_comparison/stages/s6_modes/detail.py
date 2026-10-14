"""detail — the facts of one programme (MSc DFT or another) on the aspects
asked, read against the applicant."""

from __future__ import annotations

from app.domains.specialist.program_comparison.models import Conditions
from app.domains.specialist.program_comparison.stages.s6_modes.base import program_result


class Detail:
    def assemble(self, views, fits, *, target_id, subject_ids, dimensions, conditions: Conditions):
        subject = subject_ids[0]
        return program_result(views[subject], fits.get(subject), dimensions), (), (), ()
