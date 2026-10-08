"""
S1 — the structured form of one course-recommendation request.

Everything the user's message says that the recommendation can act on:
courses they want or don't want, skills, topics and Verticals they're
after, how they like to study, and profile facts they state in passing.
Values outside the known vocabularies are dropped rather than rejected, so
one odd entry from the parsing model never costs the rest.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

Mode = Literal["degree_overview", "ad_hoc", "semester_plan"]

# The profile's track vocabulary (profile field track_interest).
TRACKS = (
    "computing_technologies",
    "financial_data_analytics_intelligence",
    "digital_financial_transactions_risk",
)
# The knowledge base's skill vocabulary (domain contracts.SkillId).
SKILLS = (
    "ai_ml", "data_analytics", "data_engineering", "finance", "payments_systems",
    "product", "programming", "regulation", "risk_modeling", "security",
)
STUDY_MODES = ("full_time", "part_time")
CAPSTONE_INTENTS = ("capstone_research", "capstone_internship", "electives_instead")

_COURSE_CODE = re.compile(r"^[A-Z]{2,4}\d{4}[A-Z]?$")
_MAX_ITEMS = 10
_MAX_KEYWORD = 60


def _keep(values, allowed) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v in allowed))


class ParsedRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Mode = "degree_overview"
    include_codes: list[str] = []
    exclude_codes: list[str] = []
    preferred_skills: list[str] = []
    keywords: list[str] = []
    vertical_preference: list[str] = []
    workload_style: Literal["less_project", "lecture"] | None = None
    # Profile facts the user stated in the message (for save suggestions).
    study_mode: Literal["full_time", "part_time"] | None = None
    capstone_intent: Literal["capstone_research", "capstone_internship", "electives_instead"] | None = None
    # True when the message couldn't be parsed and this is the default.
    parse_failed: bool = False

    @field_validator("include_codes", "exclude_codes", mode="before")
    @classmethod
    def _codes(cls, values):
        if not isinstance(values, list):
            return []
        codes = (str(v).strip().upper() for v in values if isinstance(v, str))
        return list(dict.fromkeys(c for c in codes if _COURSE_CODE.fullmatch(c)))[:_MAX_ITEMS]

    @field_validator("preferred_skills", mode="before")
    @classmethod
    def _skills(cls, values):
        return _keep(values, SKILLS)

    @field_validator("vertical_preference", mode="before")
    @classmethod
    def _tracks(cls, values):
        return _keep(values, TRACKS)

    @field_validator("keywords", mode="before")
    @classmethod
    def _keywords(cls, values):
        if not isinstance(values, list):
            return []
        words = (" ".join(str(v).split())[:_MAX_KEYWORD] for v in values if isinstance(v, str))
        return list(dict.fromkeys(w for w in words if w))[:_MAX_ITEMS]

    @field_validator("workload_style", "study_mode", "capstone_intent", mode="before")
    @classmethod
    def _optional_choice(cls, value, info):
        allowed = {
            "workload_style": ("less_project", "lecture"),
            "study_mode": STUDY_MODES,
            "capstone_intent": CAPSTONE_INTENTS,
        }[info.field_name]
        return value if value in allowed else None
