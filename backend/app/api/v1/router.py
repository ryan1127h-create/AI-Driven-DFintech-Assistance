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
from app.domains.admin import api as admin_api
from app.domains.alumni import api as alumni_api
from app.domains.checklist import api as checklist_api
from app.domains.cv_import import api as cv_import_api
from app.domains.lifecycle import api as lifecycle_api
from app.domains.profile import api as profile_api
from app.domains.programme_page import api as programme_page_api
from app.domains.reminders import api as reminders_api
from app.orchestrator import api as orchestrator_api

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])  # GET /health
router.include_router(auth_api.router, tags=["auth"])  # POST /auth/register, /auth/login, /auth/logout, GET /auth/me
router.include_router(admin_api.router, tags=["admin"])  # GET /admin/overview
router.include_router(alumni_api.router, tags=["alumni"])  # GET /alumni/matches, /alumni/requests, /alumni/me
router.include_router(checklist_api.router, tags=["checklist"])  # GET /checklist, POST /checklist/application
router.include_router(cv_import_api.router, tags=["cv-import"])  # POST /cv-import, GET /cv-import/latest
router.include_router(lifecycle_api.router, tags=["lifecycle"])  # GET /lifecycle
router.include_router(profile_api.router, tags=["profile"])  # GET/PATCH /profile, /profile/definitions, /conflicts, /consents
router.include_router(programme_page_api.router, tags=["programme"])  # GET /programme/overview (public)
router.include_router(reminders_api.router, tags=["reminders"])  # GET /reminders, POST /reminders/dismiss
router.include_router(orchestrator_api.router, tags=["chatbot"])  # POST /chat, /chat/stream, GET /chat/sessions, /chat/{id}/history, etc.
