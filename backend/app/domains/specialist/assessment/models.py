"""What the assessment computes: the hard conditions an application must
meet, the soft factors that decide how competitive it is, and the overall
verdict. Every item names the facts it was read from, so a reply can say
why."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

# A hard condition: met, not needed (e.g. English with an English-medium
# degree), needs confirming (unknown, or decided case by case), or a gap.
HardStatus = Literal["met", "exempt", "to_confirm", "gap"]
# A soft factor: already a strength, worth strengthening, or not known.
SoftStatus = Literal["strength", "improve", "unknown"]
# All hard conditions met, some still to confirm, or at least one gap.
Verdict = Literal["all_met", "to_confirm", "gap"]
# Recently graduated (or no full-time work yet) or already working.
ApplicantType = Literal["fresh_graduate", "experienced", "unknown"]


@dataclass(frozen=True)
class HardCheck:
    key: str
    status: HardStatus
    # What the official requirement says, in one line.
    requirement: str
    # Why this status — the facts it was read from, in words.
    finding: str
    # What to do about it (empty when nothing is needed).
    action: str = ""
    source_url: str = ""
    # Profile fields that would settle it, when it is to_confirm for lack of them.
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SoftFactor:
    key: str
    status: SoftStatus
    # The official statement it follows, in one line.
    basis: str
    finding: str
    action: str = ""
    source_url: str = ""
    # Not required at all (e.g. GMAT/GRE): an improvement is a suggestion.
    optional: bool = False
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssessmentResult:
    verdict: Verdict
    hard: tuple[HardCheck, ...]
    soft: tuple[SoftFactor, ...]
    applicant_type: ApplicantType
    # The soft factors that are strengths, and the (at most two) most
    # worthwhile to strengthen, by key.
    strengths: tuple[str, ...]
    improvements: tuple[str, ...]
    # Profile fields worth asking for, most decisive first.
    missing_fields: tuple[str, ...]
    intake_year: int
    application_opens: str | None
    application_closes: str | None
    # field key -> where it came from, for the facts used.
    fact_sources: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
