"""
S3 rules — which profile facts count as evidence of each skill, and how
much.

The skills are the knowledge base's role-skill vocabulary
(knowledge.tags_definition.required_skills). Every signal names one
profile field (or the student's courses) and the points it is worth;
stages/s3_evidence adds them up per skill:

  - STRONG (1.0) on its own shows the skill (status "met");
  - MODERATE (0.4) and BASIC (0.2) only add up — three moderate signals
    from different fields reach "met", fewer leave it "partial";
  - an ABSENT signal is the profile explicitly saying the skill isn't
    there ("missing" — only when nothing else counts for it).

Each field counts once per skill (its best-matching signal). Courses are
one source too, but add up: each matching course is worth the signal's
points divided by how many role tags the course carries (a course tagged
for three roles says less about any one of them), summed up to the
signal's points. No evidence at all is "unknown", never "missing".

Level anchors (field_definitions.value_labels): code_level 0-4, the other
*_level fields 1-3 — e.g. code_level 3 "has built a complete project with
tests", finance_level 3 "can explain option pricing".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SKILLS = (
    "ai_ml",
    "data_analytics",
    "data_engineering",
    "finance",
    "payments_systems",
    "product",
    "programming",
    "regulation",
    "risk_modeling",
    "security",
)

STRONG = 1.0
MODERATE = 0.4
BASIC = 0.2
# Points at which a skill counts as met.
MET_POINTS = 1.0

# Experience gained only in an internship (function_experience items
# marked internship) is worth this share of the signal's points.
INTERNSHIP_FACTOR = 0.5
# A course still being taken is worth this share of a completed one.
IN_PROGRESS_FACTOR = 0.5


def course_weight(tag_count: int) -> float:
    """The share of a course signal's points one course is worth, by how
    many role tags the course carries."""
    return 1.0 / max(tag_count, 1)

SignalKind = Literal["level", "any_of", "course_tag", "absent"]


@dataclass(frozen=True)
class Signal:
    """One way a profile fact can count toward a skill.

    level:      `field` holds a level; `levels` maps level -> points.
    any_of:     `field` (single- or multi-valued) holds any of `values`.
    course_tag: a completed (or current) course is tagged with any of `values`.
    absent:     `field` holds one of `levels`' keys — explicit absence.
    """

    kind: SignalKind
    field: str
    points: float = 0.0
    values: frozenset[str] = frozenset()
    levels: tuple[tuple[int, float], ...] = ()


def _level(field: str, **points_by_level: float) -> Signal:
    levels = tuple(sorted((int(k.removeprefix("l")), v) for k, v in points_by_level.items()))
    return Signal("level", field, levels=levels)


def _any(field: str, points: float, *values: str) -> Signal:
    return Signal("any_of", field, points=points, values=frozenset(values))


def _courses(points: float, *tags: str) -> Signal:
    return Signal("course_tag", "courses", points=points, values=frozenset(tags))


def _absent(field: str, *levels: int) -> Signal:
    return Signal("absent", field, levels=tuple((level, 0.0) for level in levels))


SKILL_SIGNALS: dict[str, tuple[Signal, ...]] = {
    "programming": (
        _level("code_level", l1=BASIC, l2=MODERATE, l3=STRONG, l4=STRONG),
        _any("function_experience", STRONG, "engineering"),
        _any("tech_stack", MODERATE, "python", "java", "cpp", "javascript", "r"),
        _any("degree_discipline_category", MODERATE, "cs_se", "information_systems"),
        _any("prior_coursework", MODERATE, "programming", "dsa"),
        _courses(MODERATE, "software_engineering"),
        _absent("code_level", 0),
    ),
    "ai_ml": (
        _level("ml_ai_level", l1=BASIC, l2=MODERATE, l3=STRONG),
        _any("function_experience", STRONG, "data_ai"),
        _any("prior_coursework", MODERATE, "machine_learning"),
        _courses(MODERATE, "machine_learning_ai"),
    ),
    "data_analytics": (
        _any("function_experience", STRONG, "data_ai"),
        _level("math_stats_level", l1=BASIC, l2=MODERATE, l3=MODERATE),
        _any("tech_stack", MODERATE, "sql", "r", "tableau_powerbi", "excel_vba"),
        _any("prior_coursework", MODERATE, "probability_statistics", "econometrics"),
        _any("degree_discipline_category", MODERATE, "math_stats_physics"),
        _courses(MODERATE, "data_analytics"),
    ),
    "data_engineering": (
        _level("data_engineering_level", l1=BASIC, l2=MODERATE, l3=STRONG),
        _any("tech_stack", MODERATE, "spark", "sql", "cloud", "docker"),
        _any("certifications", MODERATE, "cloud_cert"),
        _any("prior_coursework", MODERATE, "databases"),
        _courses(MODERATE, "data_engineering"),
    ),
    "finance": (
        _level("finance_level", l1=BASIC, l2=MODERATE, l3=STRONG),
        _any("certifications", STRONG, "cfa", "cpa_acca"),
        # CFA levels passed without the charter (the tools layer marks them "_partial").
        _any("certifications", MODERATE, "cfa_partial"),
        _any("function_experience", MODERATE, "quant"),
        _any("degree_discipline_category", MODERATE, "finance_econ_accounting"),
        _any("prior_coursework", MODERATE, "corporate_finance", "investments_derivatives", "accounting"),
        _any("domain_knowledge", MODERATE, "capital_markets", "derivatives", "wealth_insurtech"),
        # Quantitative-finance courses count toward risk modelling only.
        _courses(MODERATE, "finance_investment"),
    ),
    "risk_modeling": (
        _any("certifications", STRONG, "frm"),
        _any("certifications", MODERATE, "frm_partial"),  # Part 1 only
        _any("function_experience", STRONG, "quant"),
        _any("domain_knowledge", MODERATE, "risk_management", "derivatives"),
        _any("prior_coursework", MODERATE, "stochastic_calculus", "investments_derivatives"),
        _level("math_stats_level", l3=MODERATE),
        _courses(MODERATE, "risk_management", "quantitative_finance"),
    ),
    "regulation": (
        _any("function_experience", MODERATE, "risk_compliance"),
        _any("domain_knowledge", MODERATE, "aml_compliance"),
        _courses(MODERATE, "regulation_governance"),
    ),
    "security": (
        _courses(MODERATE, "cybersecurity"),
    ),
    "payments_systems": (
        _level("blockchain_level", l1=BASIC, l2=MODERATE, l3=STRONG),
        _any("domain_knowledge", MODERATE, "payments", "digital_banking", "digital_assets"),
        _any("tech_stack", MODERATE, "solidity"),
        _courses(MODERATE, "blockchain"),
    ),
    "product": (
        _any("function_experience", STRONG, "product_business"),
        _any("degree_discipline_category", MODERATE, "business_mgmt"),
        _courses(MODERATE, "product_business", "entrepreneurship"),
    ),
}

# The profile fields the signals read — what the input contract carries.
EVIDENCE_FIELDS = frozenset(
    signal.field for signals in SKILL_SIGNALS.values() for signal in signals if signal.field != "courses"
)
