"""
STAGE 2/3/4 shared knowledge — the NUS MSc DFinTech programme structure,
transcribed 1:1 from knowledge.document_chunks (source_table='course_rules',
intake='2026-08-onwards') into executable constants.

Mirrors knowledge_retrieval/service.py::_CURRENT_INTAKE — update both
together when a new cohort's rules ship (see rule:cur_cohort_2026_vs_2025;
the previous cohort's mandatory set was BMD5301/BMD5302/IT5001/IT5003
instead of BMD5301/BMD5302/IT5001X/IT5006).

This is programme POLICY, not a physical property of a course row viewed in
isolation — it lives here (in the domain that interprets it), not as a new
database column, deliberately mirroring the existing _CURRENT_INTAKE
precedent rather than reopening the "who owns this data" question already
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

# rule:cur_degree_structure
TOTAL_PROGRAMME_UNITS = 52
CORE_UNITS = 28
CAPSTONE_UNITS = 12
ELECTIVE_UNITS_BASE = 12  # +12 more (24 total) once the elective-alternative path is active

# Typical module credit for one elective — used only to translate a units
# shortfall into an approximate course COUNT for a recommendation slot's
# required_pick_count. Never used to validate an actual unit total.
TYPICAL_ELECTIVE_UNITS = 4

# STAGE 5 scoring: free-text keyword hints that a student wants to avoid
# heavy independent-project coursework (see pipeline/scoring.py). Not
# exhaustive — a keyword table, not an NLP model.
PROJECT_AVERSE_KEYWORDS = (
    "少项目",
    "不想太多project",
    "不想要太多project",
    "少做项目",
    "偏好课堂",
    "偏好讲授",
    "discussion-based",
    "discussion based",
    "less project",
    "fewer project",
    "lecture-based",
    "lecture based",
    "avoid project",
)
