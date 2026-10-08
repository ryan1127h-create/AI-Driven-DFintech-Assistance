"""
Tunable recommendation parameters — scoring weights and presentation
sizes. Unlike policy/curriculum.py (programme rules transcribed from the
knowledge base), every value here is a design choice that can be adjusted
without any rule changing. Change them here only; the stages read them.
"""

from __future__ import annotations

# S5 scoring weights (stages/s5_scoring/scorer.py).
W_GAP_SKILL = 2.0
W_ROLE_SKILL = 1.0
W_PREFERENCE = 1.5
W_CURATED_ROLE = 1.0
PROJECT_HEAVY_PENALTY = -1.0

# How many top-scored candidates are considered when picking the best PAIR
# for a 2-pick slot — the eligible pool per slot is always small (a
# handful of courses), so this stays cheap.
PAIR_CANDIDATE_WINDOW = 4

# S4: the most picks any one requirement group asks for at a time.
MAX_PICKS_PER_SLOT = 2

# S4: how many more candidates to show beyond what's strictly
# required, so the student gets real choice instead of one pre-made
# decision (fixed +2, capped by how many eligible candidates exist).
EXTRA_DISPLAY_OPTIONS = 2

# S5 scoring: free-text keyword hints that a student wants to avoid
# heavy independent-project coursework (see stages/s3_constraints/catalog.py
# is_project_averse()). Not exhaustive — a keyword table, not an NLP model.
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

# S5 recommendation evidence (stages/s5_scoring/evidence.py): a skill is
# only named as a reason when at most this share of the recommendable
# catalogue carries it — "programming" (on ~90% of courses) says nothing
# about why one course fits better than another.
DISTINCTIVE_SKILL_MAX_SHARE = 0.5

# Longest course synopsis (the description's opening sentences) handed to
# the reply as the only source for what a course teaches.
SYNOPSIS_MAX_CHARS = 280
