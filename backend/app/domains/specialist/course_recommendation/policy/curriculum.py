"""
S3/S4 shared knowledge — the NUS MSc DFinTech programme structure,
transcribed 1:1 from knowledge.document_chunks (source_table='course_rules',
intake='2026-08-onwards') into executable constants.

Mirrors knowledge_retrieval/service.py::CURRENT_CURRICULUM_INTAKE (a
test keeps the two equal) — update both together when a new cohort's
rules ship (see rule:cur_cohort_2026_vs_2025;
the previous cohort's mandatory set was BMD5301/BMD5302/IT5001/IT5003
instead of BMD5301/BMD5302/IT5001X/IT5006).

This is programme POLICY, not a physical property of a course row viewed in
isolation — it lives here (in the domain that interprets it), not as a new
database column, deliberately mirroring CURRENT_CURRICULUM_INTAKE
rather than reopening the "who owns this data" question already
on hold pending the external pipeline maintainer.
"""

from __future__ import annotations

CURRENT_INTAKE = "2026-08-onwards"

# rule:cur_core_composition — any 3 of these 11 (12 units)
CORE_CHOICE_POOL = frozenset(
    {
        "FT5001",
        "FT5002",
        "FT5003",
        "FT5004",
        "FT5005",
        "FT5009",
        "FT5010",
        "FT5011",
        "FT5012",
        "FT5013",
        "FT5014",
    }
)
CORE_CHOICE_REQUIRED_COUNT = 3

# rule:cur_core_composition + cur_cohort_2026_vs_2025 — all 4 required (16 units)
CORE_MANDATORY = frozenset({"BMD5301", "BMD5302", "IT5001X", "IT5006"})

# rule:cur_replacement_policy — only replaces BMD5301 or IT5001X, and only
# with prior School of Computing approval. Completion alone never proves
# approval, so degree_progress.py raises this as a caution, never a
# satisfied requirement. Every one of these 4 codes also carries a real
# `vertical` tag today (course_electives), so catalog.classify() resolves
# them to "elective" first — see that module's docstring for why the
# ordering matters.
CORE_MANDATORY_REPLACEMENTS = frozenset({"IT5003", "IT5004", "IT5005", "IT5008"})

# rule:cur_capstone_options
CAPSTONE_CODE = "FT5007"
CAPSTONE_ALTERNATIVE_ELECTIVE_COUNT = 3  # 3 extra electives (12 units) replace it

# rule:cur_elective_rules — level 6000+ never counts; excess 4000-level don't count
MAX_LEVEL_4000_ELECTIVES = 2
MIN_COUNTABLE_ELECTIVE_LEVEL = 4000
NON_COUNTABLE_LEVEL = 6000  # this level and above never counts toward the degree

# The elective Verticals by the profile's track keys (profile fields
# track_interest / track_chosen) -> their names in the catalogue
# (knowledge.course_electives).
TRACK_VERTICALS = {
    "computing_technologies": "Vertical #1. Computing Technologies",
    "financial_data_analytics_intelligence": "Vertical #2. Financial Data Analytics and Intelligence",
    "digital_financial_transactions_risk": "Vertical #3. Digital Financial Transactions and Risk Management",
}

# Semester unit load, by study mode (MSc DFinTech programme structure,
# comp.nus.edu.sg): full-time 12-20 units, part-time 4-12. The defaults
# are the recommended course plans' usual semester (16 full-time, 8
# part-time), used when the student doesn't say how many units they want.
UNIT_LOAD = {
    "full_time": {"min": 12, "max": 20, "default": 16},
    "part_time": {"min": 4, "max": 12, "default": 8},
}

# The Capstone (12 units) spans two semesters. ASSUMPTION, to verify: it
# counts 6 units toward each semester's load — which fits the programme's
# recommended plans (12 + 6 = 18 units in each Capstone semester).
CAPSTONE_UNITS_PER_SEMESTER = 6

# rule:cur_degree_structure
TOTAL_PROGRAMME_UNITS = 52
ELECTIVE_UNITS_BASE = 12  # +12 more (24 total) once the elective-alternative path is active

# Typical module credit for one elective — used only to translate a units
# shortfall into an approximate course COUNT for a recommendation slot's
# required_pick_count. Never used to validate an actual unit total.
TYPICAL_ELECTIVE_UNITS = 4
