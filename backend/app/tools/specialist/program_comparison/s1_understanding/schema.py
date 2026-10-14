"""
S1 — the structured form of one comparison request: what kind of answer
is wanted, the catalogue programmes the message names (as program ids),
the aspects it asks about and the conditions or facts it states in
passing. Values outside the known vocabularies are dropped rather than
rejected, so one odd entry from the parsing model never costs the rest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

MODES = ("compare", "detail", "explore")
DIMENSIONS = ("cost", "duration", "curriculum", "admission", "flexibility", "funding", "deadlines", "location")
STUDY_MODES = ("full_time", "part_time", "online")
CATEGORIES = ("fintech", "quant_finance", "financial_engineering", "finance", "business_analytics", "computing")

# More than can be compared, so the builder can say which were left out.
_MAX_PROGRAMS = 8


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))


class ParsedComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Literal["compare", "detail", "explore"] | None = None
    # Program ids the message names, in the order named (MSc DFT included
    # when named); the parser keeps only ids from the catalogue it was given.
    programs: list[str] = []
    # Programmes or universities named that the catalogue doesn't hold, verbatim.
    unmatched_programs: list[str] = []
    dimensions: list[str] = []
    countries: list[str] = []
    study_mode: Literal["full_time", "part_time", "online"] | None = None
    categories: list[str] = []
    # A role family tag the message names as the applicant's goal.
    role: str | None = None
    # The academic year the applicant says they will start (AY2027/28 -> 2027).
    intake_year: int | None = None
    parse_failed: bool = False

    @field_validator("programs", "unmatched_programs", mode="before")
    @classmethod
    def keep_names(cls, value) -> list[str]:
        return _strings(value)[:_MAX_PROGRAMS]

    @field_validator("dimensions", mode="before")
    @classmethod
    def keep_dimensions(cls, value) -> list[str]:
        return [v for v in _strings(value) if v in DIMENSIONS]

    @field_validator("categories", mode="before")
    @classmethod
    def keep_categories(cls, value) -> list[str]:
        return [v for v in _strings(value) if v in CATEGORIES]

    @field_validator("countries", mode="before")
    @classmethod
    def keep_countries(cls, value) -> list[str]:
        return [v.upper() for v in _strings(value) if len(v) == 2 and v.isalpha()]

    @field_validator("mode", "study_mode", "role", mode="before")
    @classmethod
    def drop_unknown(cls, value, info):
        if not isinstance(value, str) or not value.strip():
            return None
        allowed = {"mode": MODES, "study_mode": STUDY_MODES}.get(info.field_name)
        return value if allowed is None or value in allowed else None

    @field_validator("intake_year", mode="before")
    @classmethod
    def keep_year(cls, value):
        return value if isinstance(value, int) and 2024 <= value <= 2035 else None
