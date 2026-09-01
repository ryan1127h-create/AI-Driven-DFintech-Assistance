"""
Central route registry for app's API surface — the one place that
lists every mounted domain and system endpoint. Each domain owns its own
APIRouter (its api.py) and knows nothing about the others; this file is
the only place that wires the HTTP surface together, so "what endpoints
exist" is answered by reading this one file.

To mount a new domain: give it its own api.py exposing
`router = APIRouter()`, then add one `include_router(...)` line below.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.domains.auth import api as auth_api
from app.domains.career_planning import api as career_planning_api
from app.domains.checklist import api as checklist_api
from app.domains.course_catalog import api as course_catalog_api
from app.domains.course_recommendation import api as course_recommendation_api
from app.domains.profile import api as profile_api
from app.domains.program_comparison import api as program_comparison_api
from app.orchestrator import api as orchestrator_api

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])  # GET /health
router.include_router(auth_api.router, tags=["auth"])  # POST /auth/register, /auth/login, /auth/logout, GET /auth/me
router.include_router(checklist_api.router, tags=["checklist"])  # GET /checklist, PATCH/POST/GET /checklist/items/{item_id}[/file]
router.include_router(profile_api.router, tags=["profile"])  # GET/PATCH/POST /profile, POST /profile/resume
router.include_router(course_recommendation_api.router, tags=["course_recommendation"])  # POST /course-recommendations
router.include_router(course_catalog_api.router, tags=["course_catalog"])  # GET /courses
router.include_router(program_comparison_api.router, tags=["program_comparison"])  # GET/POST /program-comparisons
router.include_router(career_planning_api.router, tags=["career_planning"])  # POST /career-plans
router.include_router(orchestrator_api.router, tags=["chatbot"])  # POST /chat, /chat/stream, GET /chat/sessions, /chat/{id}/history, etc.
