"""
Program-comparison orchestration. Reads no data itself: the caller (the
tools layer) supplies the knowledge-base chunks, the target role's skills
and the applicant facts.

Straight-line flow:

    1. resolve which programmes to compare (default: NUS + all competitors)
    2. build the raw facts table            facts.py, pure code
    3. compute personal match scores        match_scorer.py, pure code
    4. LLM rewrites cells + comments        comparison_agent.py
         on failure -> raw text cells, still answers
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.specialist.program_comparison import comparison_agent, facts, match_scorer
from app.domains.specialist.program_comparison._legacy_models import ProgramFacts, ProgramMatch

SUPPORTED_DIMENSIONS = ("curriculum", "fees", "admission")
DEFAULT_DIMENSIONS = list(SUPPORTED_DIMENSIONS)

# The one requestable dimension we have no data for yet.
_NO_DATA_DIMENSION = "career"

_ADVISORY_NOTE = (
    "This comparison is compiled by this project from each university's "
    "public pages for reference — always confirm with the official sites; "
    "fees and deadlines change between intakes."
)


@dataclass(frozen=True)
class ComparisonResult:
    """What compare_programs() returns to interface.py."""
    dimensions: tuple[str, ...]
    programs: tuple[str, ...]
    cells: dict[str, dict[str, str]]  # dimension -> programme -> cell text
    match_scores: tuple[ProgramMatch, ...]
    comments: dict[str, str]  # programme -> suitability comment
    summary: str
    notes: tuple[str, ...]
    sources: tuple[str, ...]


def compare_programs(
    chunks: list[dict],
    programs: list[str] | None = None,
    focus: list[str] | None = None,
    target_role: str | None = None,
    role_skills: list[str] | None = None,
    applicant: dict | None = None,
) -> ComparisonResult:
    """`chunks`: every knowledge-base chunk; `role_skills`: the target
    role's skills (empty when the role is unknown); `applicant`:
    {"has_gmat_gre": bool | None, "work_years": int | None}, None meaning
    not known."""
    notes: list[str] = []
    known = [facts.build_nus(chunks)] + facts.build_competitors(chunks)

    # 1. Which programmes and which dimensions.
    selected = _select_programs(known, programs or [], notes)
    dimensions = _select_dimensions(focus or [], notes)

    # 2. Raw facts table (pure code).
    table = {
        dim: {p.name: p.dimension_text.get(dim, "") for p in selected}
        for dim in dimensions
    }

    # 3. Personal match scores (pure code).
    role_skills = list(role_skills or [])
    if target_role and not role_skills:
        notes.append(
            f"'{target_role}' is not one of the known role families, so the "
            "skill-focus component was excluded from personal match scores."
        )
    matches = match_scorer.score_programs(selected, role_skills, applicant)

    # 4. LLM presentation with raw-text fallback.
    cells, comments, summary, agent_notes = comparison_agent.present(table, selected, matches)
    notes.extend(agent_notes)
    notes.append(_ADVISORY_NOTE)

    sources = []
    for p in selected:
        for url in p.source_urls:
            if url not in sources:
                sources.append(url)

    return ComparisonResult(
        dimensions=tuple(dimensions),
        programs=tuple(p.name for p in selected),
        cells=cells,
        match_scores=tuple(matches),
        comments=comments,
        summary=summary,
        notes=tuple(notes),
        sources=tuple(sources),
    )


def _select_programs(known: list[ProgramFacts], requested: list[str], notes: list[str]) -> list[ProgramFacts]:
    """Empty request -> NUS + all competitors. Otherwise case-insensitive
    substring match against known names; unknown names are noted, NUS is
    always included as the baseline."""
    if not any(name.strip() for name in requested):
        return known

    selected = [known[0]]  # NUS baseline
    for name in requested:
        wanted = name.strip().lower()
        if not wanted:
            continue
        match = next(
            (p for p in known if wanted in p.name.lower() or p.name.lower() in wanted),
            None,
        )
        if match is None:
            notes.append(f"'{name}' is not in our comparison data "
                         "(available: " + "; ".join(p.name for p in known) + ").")
        elif match not in selected:
            selected.append(match)
    return selected


def _select_dimensions(requested: list[str], notes: list[str]) -> list[str]:
    """Empty request -> all supported dimensions. career has no data yet and
    is answered with a note instead of an empty table row."""
    if not requested:
        return DEFAULT_DIMENSIONS

    dimensions = [d for d in requested if d in SUPPORTED_DIMENSIONS]
    if _NO_DATA_DIMENSION in requested:
        notes.append("Career-outcome data is not in the knowledge base yet, "
                     "so the 'career' dimension cannot be compared.")
    return dimensions or DEFAULT_DIMENSIONS
