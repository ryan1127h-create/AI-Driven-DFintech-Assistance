from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.program_comparison import service
from app.domains.program_comparison.schemas import (
    ComparisonOptionsResponse,
    ComparisonRow,
    ProgramComparisonRequest,
    ProgramComparisonResponse,
    ProgramMatchScore,
)

router = APIRouter()


@router.get("/program-comparisons/options", response_model=ComparisonOptionsResponse)
def get_comparison_options() -> ComparisonOptionsResponse:
    """Dropdown options for the comparison form: the exact programme names
    we have data for, and the supported dimensions. Frontend should use
    these instead of free-text input."""
    return ComparisonOptionsResponse(**service.list_options())


# Sync `def` on purpose: the service does blocking DB + LLM calls, and
# FastAPI runs sync path operations in a threadpool.
@router.post("/program-comparisons", response_model=ProgramComparisonResponse)
def compare_programs(
    request: ProgramComparisonRequest,
    user_id: str = Depends(get_current_user_id),
) -> ProgramComparisonResponse:
    """
    Side-by-side programme comparison plus a personal match score for the
    current authenticated user.
    Facts and scores are computed by code from the knowledge base; the LLM
    only rewrites table cells and comments, with a raw-text fallback.
    """
    result = service.compare_programs(
        user_id=user_id,
        programs=request.programs,
        focus=request.focus,
        target_role=request.target_role,
    )

    return ProgramComparisonResponse(
        programs=list(result.programs),
        comparison_table=[
            ComparisonRow(dimension=dim, values=result.cells[dim])
            for dim in result.dimensions
        ],
        match_scores=[ProgramMatchScore(**asdict(m)) for m in result.match_scores],
        program_comments=result.comments,
        best_fit_summary=result.summary,
        notes=list(result.notes),
        sources=list(result.sources),
    )
