"""
S2 — the data prefetch.py gathers for one turn, handed to builder.py.
Kept in its own module so the builder can depend on this shape without
depending, even indirectly, on the profile or knowledge-base interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Skill-level fields rendered into the report's tech_level text, with the
# name each is shown under.
LEVEL_FIELDS = (
    ("code_level", "Programming"),
    ("ml_ai_level", "Machine learning"),
    ("math_stats_level", "Maths & statistics"),
    ("finance_level", "Finance"),
    ("data_engineering_level", "Data engineering"),
    ("blockchain_level", "Blockchain"),
)
# Every profile fact the report shows as text — the facts prefetch.py
# renders into Prefetched.fact_labels.
LABELLED_FIELDS = (
    "degree_discipline_category",
    "prior_coursework",
    *(key for key, _ in LEVEL_FIELDS),
    "tech_stack",
)


@dataclass(frozen=True)
class Prefetched:
    # Profile facts for the "course" purpose ({} without consent or when
    # the profile couldn't be read), and each fact's English display text.
    facts: dict
    fact_labels: dict[str, str]
    # Display name of each role tag in the profile's target_role_families.
    role_labels: dict[str, str]
    readiness_notes: tuple[str, ...]
    graduation_notes: tuple[str, ...]
    role_tag: str | None
    # The role tag the message itself named, when it named a known one.
    stated_role_tag: str | None
    role_profile: dict | None
    courses: list[dict]
    curriculum_rules: list[dict]
    course_tags: dict[str, list[str]]
    role_tags: list[dict]
    course_electives: dict[str, list[str]]
    # Limitations met while gathering (e.g. the profile couldn't be read),
    # passed on to the reply's notes.
    notes: tuple[str, ...] = field(default_factory=tuple)
