"""
Match scorer — pure code, no LLM, no I/O. Quantifies how well each
programme fits THIS user (their skills goal, test scores, work situation).
It is a personal-fit reference, not a programme ranking.

Three components (weights sum to 1):
  skill_focus   0.5  how many of the user's role skills the programme's
                     curriculum text mentions (keyword scan)
  test_scores   0.3  user already has GMAT/GRE -> fine everywhere; if not,
                     programmes that don't force a score fit better
  flexibility   0.2  user has work experience -> part-time option matters

Honesty rule: a component with missing data is EXCLUDED (included=False,
evidence says why) and the total is re-weighted over what remains — we
never invent a number. No data at all -> total is None.
"""

from __future__ import annotations

from app.modules.program_comparison.models import ProgramFacts, ProgramMatch, SubScore

W_SKILL_FOCUS = 0.5
W_TEST_SCORES = 0.3
W_FLEXIBILITY = 0.2

# Skill tag -> keywords looked up (case-insensitively) in curriculum text.
_SKILL_KEYWORDS = {
    "ai_ml": ("machine learning", "artificial intelligence", "ai"),
    "data_analytics": ("analytics", "data science", "data analysis"),
    "finance": ("finance", "financial"),
    "payments_systems": ("payment", "blockchain", "trading"),
    "product": ("product", "business", "innovation"),
    "programming": ("programming", "software", "computing", "coding"),
    "regulation": ("regulation", "regulatory", "compliance"),
    "risk_modeling": ("risk",),
    "security": ("security", "cyber"),
}

# Phrases meaning a GMAT/GRE score is NOT strictly required. Checked before
# _TEST_REQUIRED because texts like "recommended but not compulsory" contain
# signals for both.
_TEST_OPTIONAL = ("not compulsory", "not required", "optional", "recommended")
_TEST_REQUIRED = ("require", "must", "prerequisite")

# Work experience from which part-time flexibility is assumed to matter.
MIN_WORK_YEARS_FOR_FLEXIBILITY = 2


def score_programs(
    programs: list[ProgramFacts],
    role_skills: list[str],
    profile: dict | None,
) -> list[ProgramMatch]:
    return [_score_one(p, role_skills, profile or {}) for p in programs]


def _score_one(program: ProgramFacts, role_skills: list[str], profile: dict) -> ProgramMatch:
    subscores = (
        _skill_focus(program, role_skills),
        _test_scores(program, profile),
        _flexibility(program, profile),
    )

    included = [s for s in subscores if s.included]
    total = None
    if included:
        weight_sum = sum(s.weight for s in included)
        total = round(sum(s.score * s.weight for s in included) / weight_sum)

    return ProgramMatch(program=program.name, total=total, subscores=subscores)


def _skill_focus(program: ProgramFacts, role_skills: list[str]) -> SubScore:
    if not role_skills:
        return SubScore("skill_focus", W_SKILL_FOCUS, 0, False,
                        "No target role skills to match against.")
    text = program.dimension_text.get("curriculum", "").lower()
    if not text:
        return SubScore("skill_focus", W_SKILL_FOCUS, 0, False,
                        "No curriculum information for this programme.")

    matched = [
        skill for skill in role_skills
        if any(kw in text for kw in _SKILL_KEYWORDS.get(skill, ()))
    ]
    score = round(100 * len(matched) / len(role_skills))
    return SubScore(
        "skill_focus", W_SKILL_FOCUS, score, True,
        f"Curriculum mentions {len(matched)}/{len(role_skills)} of your role "
        f"skills ({', '.join(matched) or 'none'}).",
    )


def _test_scores(program: ProgramFacts, profile: dict) -> SubScore:
    if profile.get("gmat") is not None or profile.get("gre") is not None:
        return SubScore("test_scores", W_TEST_SCORES, 100, True,
                        "You already have a GMAT/GRE score on file.")

    text = program.dimension_text.get("admission", "").lower()
    if "gmat" not in text and "gre" not in text:
        return SubScore("test_scores", W_TEST_SCORES, 0, False,
                        "No GMAT/GRE requirement information for this programme.")
    if any(phrase in text for phrase in _TEST_OPTIONAL):
        return SubScore("test_scores", W_TEST_SCORES, 80, True,
                        "You have no GMAT/GRE score yet, and this programme "
                        "does not strictly require one.")
    if any(phrase in text for phrase in _TEST_REQUIRED):
        return SubScore("test_scores", W_TEST_SCORES, 30, True,
                        "You have no GMAT/GRE score yet, and this programme's "
                        "admission text points to one being required.")
    return SubScore("test_scores", W_TEST_SCORES, 0, False,
                    "GMAT/GRE policy for this programme could not be determined.")


def _flexibility(program: ProgramFacts, profile: dict) -> SubScore:
    work_years = profile.get("work_years")
    if work_years is None:
        return SubScore("flexibility", W_FLEXIBILITY, 0, False,
                        "No work-experience information in your profile.")
    if work_years < MIN_WORK_YEARS_FOR_FLEXIBILITY:
        return SubScore("flexibility", W_FLEXIBILITY, 0, False,
                        "Little work experience on file — part-time "
                        "flexibility not treated as a factor for you.")

    text = program.dimension_text.get("curriculum", "").lower()
    if "part-time" in text or "part time" in text:
        return SubScore("flexibility", W_FLEXIBILITY, 100, True,
                        "Offers a part-time mode, useful given your work experience.")
    return SubScore("flexibility", W_FLEXIBILITY, 0, False,
                    "No part-time information found for this programme.")
