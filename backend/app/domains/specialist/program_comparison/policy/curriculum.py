"""
Curriculum coverage read against skills: which of a target role's skills
a programme teaches and how certainly, and how deep it goes on the
technology and finance sides (the "tech_depth" / "finance_depth" decision
factors).

Coverage levels, most to least certain that a student meets the skill:
required (everyone takes it), core_option (one of a restricted core list),
elective. A skill the catalogue has no entry for is unknown — its
electives may simply not be published — never "not taught".
"""

from __future__ import annotations

from dataclasses import dataclass

TECH_SKILLS = ("programming", "ai_ml", "data_engineering", "security", "payments_systems")
FINANCE_SKILLS = ("finance", "risk_modeling", "regulation")


@dataclass(frozen=True)
class SkillCoverage:
    skill: str
    coverage: str | None  # None: unknown
    courses: tuple[str, ...]


@dataclass(frozen=True)
class SkillMatch:
    skills: tuple[SkillCoverage, ...]

    def _with(self, levels) -> tuple[str, ...]:
        return tuple(s.skill for s in self.skills if s.coverage in levels)

    @property
    def guaranteed(self) -> tuple[str, ...]:
        return self._with(("required",))

    @property
    def available(self) -> tuple[str, ...]:
        return self._with(("core_option", "elective"))

    @property
    def not_taught(self) -> tuple[str, ...]:
        return self._with(("none",))

    @property
    def unknown(self) -> tuple[str, ...]:
        return tuple(s.skill for s in self.skills if s.coverage is None)


def match(curriculum: list[dict], skills: list[str] | tuple[str, ...]) -> SkillMatch:
    """`curriculum`: [{skill_id, coverage, evidence_courses}]."""
    by_skill = {area["skill_id"]: area for area in curriculum}
    return SkillMatch(tuple(
        SkillCoverage(
            skill,
            by_skill[skill]["coverage"] if skill in by_skill else None,
            tuple(by_skill[skill].get("evidence_courses") or ()) if skill in by_skill else (),
        )
        for skill in skills
    ))


def depth(curriculum: list[dict]) -> dict[str, SkillMatch]:
    return {"tech": match(curriculum, TECH_SKILLS), "finance": match(curriculum, FINANCE_SKILLS)}
