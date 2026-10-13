"""
S1 — the structured form of one career request: the roles the message
names (as role tags) and the situation facts it states in passing. Values
outside the known vocabularies are dropped rather than rejected, so one
odd entry from the parsing model never costs the rest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

# The profile's vocabularies for the facts a message may state.
JOB_SEARCH_TIMELINES = ("during_program", "right_after", "1yr_plus_later", "not_job_seeking")
INTERNSHIP_STATUSES = ("none", "searching", "secured", "completed")
MARKETS = ("SG", "CN", "IN", "HK", "SEA_OTHER", "US", "EUROPE", "OTHER", "ANY")

_MAX_ROLES = 3


class ParsedCareerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Role tags the message names, in the order named; the parser keeps
    # only tags from the catalogue it was given.
    roles: list[str] = []
    # Role phrases the message names that match none of the role families.
    unmatched_roles: list[str] = []
    job_search_timeline: Literal["during_program", "right_after", "1yr_plus_later", "not_job_seeking"] | None = None
    internship_status: Literal["none", "searching", "secured", "completed"] | None = None
    target_markets: list[str] = []
    parse_failed: bool = False

    @field_validator("roles", "unmatched_roles", mode="before")
    @classmethod
    def keep_strings(cls, value) -> list[str]:
        if not isinstance(value, list):
            return []
        return list(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))[:_MAX_ROLES]

    @field_validator("target_markets", mode="before")
    @classmethod
    def keep_markets(cls, value) -> list[str]:
        if not isinstance(value, list):
            return []
        return list(dict.fromkeys(v for v in value if v in MARKETS))

    @field_validator("job_search_timeline", "internship_status", mode="before")
    @classmethod
    def drop_unknown(cls, value, info):
        allowed = JOB_SEARCH_TIMELINES if info.field_name == "job_search_timeline" else INTERNSHIP_STATUSES
        return value if value in allowed else None
