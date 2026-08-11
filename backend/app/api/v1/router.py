"""
Central route registry for API v1 — the one place that lists every business
module and system endpoint mounted under /api/v1. Each business module
under app/modules/ owns its own APIRouter (its `api.py`) and knows nothing
about the others — chatbot and profile don't import each other's routes,
services, or repositories, only whatever a module chooses to expose via its
`interface.py` (see app/modules/profile/interface.py). This file is the only
place that wires the HTTP surface together, so "what endpoints exist" is
answered by reading this one file instead of grepping the codebase.

To add a new business module: create app/modules/<name>/ with its own
`api.py` exposing `router = APIRouter()`, then add one
`include_router(...)` line below.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.career_planning import api as career_api
from app.modules.chatbot import api as chatbot_api
from app.modules.checklist import api as checklist_api
from app.modules.course_recommendation import api as course_api
from app.modules.profile import api as profile_api
from app.modules.program_comparison import api as comparison_api

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])         # GET /health
router.include_router(chatbot_api.router, tags=["chatbot"])   # POST /chat, DELETE /chat/{session_id}
router.include_router(profile_api.router, tags=["profile"])   # GET/PATCH /profile, POST /profile/resume
router.include_router(checklist_api.router, tags=["checklist"])  # GET /checklist, PATCH /checklist/items/{item_id}
router.include_router(course_api.router, tags=["course_recommendation"])  # POST /course-recommendations
router.include_router(comparison_api.router, tags=["program_comparison"])  # GET/POST /program-comparisons
router.include_router(career_api.router, tags=["career_planning"])  # POST /career-plans
