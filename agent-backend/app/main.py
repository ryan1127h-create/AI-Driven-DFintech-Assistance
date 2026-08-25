from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Agentic AI assistant for NUS MSc DFT ",
    version="0.1.0",
)


@app.on_event("startup")
def _warm_knowledge_base_caches() -> None:
    """Best-effort cache warming for the several unsynchronized lazy
    module-level singletons the chatbot/course_recommendation/
    program_comparison modules share (knowledge_repository._CHUNKS,
    rag_service._BM25, and each module's own parsed-chunk caches) — see
    app/clients/postgres_client.py's docstring for why concurrent first-use
    of these is a real (if narrow) risk under bursty load. Priming them here,
    before the app accepts traffic, turns "racy on the first concurrent
    request" into "already warm". Never blocks startup on failure (e.g. the
    knowledge DB being briefly unreachable in a dev environment) — a cold
    cache just means the first real request pays the (harmless, just slower)
    lazy-init cost instead."""
    try:
        from app.repositories.knowledge_repository import fetch_all_chunks
        from app.services.rag_service import retrieve

        fetch_all_chunks()
        retrieve("programme overview", top_k=1)  # also primes the BM25 index

        from app.modules.course_recommendation import repository as course_repo
        course_repo.load_courses()
        course_repo.load_career_roles()
        course_repo.load_curriculum_rules()

        from app.modules.program_comparison import repository as comparison_repo
        comparison_repo.load_competitors()
        comparison_repo.load_nus()
    except Exception as exc:
        print(f"[main] Warning: startup cache warming failed (will lazy-init on first request) — {exc}")

# CORS — allowed origins come from settings.cors_allow_origins (see
# app/core/config.py for why this isn't "*": that combined with
# allow_credentials=True effectively allows any origin with credentials,
# since browsers resolve the invalid wildcard+credentials combination by
# reflecting the request's Origin header verbatim).
_cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "phase": 2,
        "status": "running",
        "docs": "/docs",
    }
