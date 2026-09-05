"""
Runtime configuration, read once from the environment (see the repo-root
.env). Every other module that needs a configurable value reads it from
`settings`, imported from here — no module reads os.environ directly, so
every knob the app has is discoverable by reading this one file.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = "MSc DFT AI Assistant"

    # DeepSeek — OpenAI-API-compatible chat-completion backend used by every
    # LLM call in the app (see app/adapters/deepseek_adapter.py). Default
    # model is deepseek-chat (DeepSeek-V3's non-reasoning endpoint) — every
    # call site wants a direct answer, not a visible chain-of-thought.
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Auth — self-issued JWT access tokens (see
    # app/domains/auth/security.py). Signing algorithm is fixed at
    # HS256; there's no reason for this project to vary it.
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_access_token_expire_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))  # 7 days
    )

    # Conversation storage — the Supabase Postgres project holding
    # student.users and every other per-user table (profiles, checklist
    # items, conversations, ...).
    conversation_database_url: str = os.getenv("CONVERSATION_DATABASE_URL", "")

    # Knowledge base — read-only connection to the separate Supabase project
    # holding the RAG corpus (schema `app`, table `document_chunks`) plus
    # the course/career-role/curriculum-rule chunks course_recommendation
    # parses. Only SELECT statements are ever issued against it.
    knowledge_database_url: str = os.getenv("KNOWLEDGE_DATABASE_URL", "")

    # Query-time embeddings for hybrid retrieval — unrelated to DeepSeek.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # How long a retrieval result stays cached before being recomputed.
    retrieval_cache_ttl_seconds: int = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "21600"))

    # Cache / session / token-blacklist store.
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Chat session storage — which ConversationStore backend the
    # orchestrator uses (see orchestrator/conversation_repository.py):
    # "memory" (default, no Redis required), "redis", or "supabase_cached".
    session_store_backend: str = os.getenv("SESSION_STORE_BACKEND", "memory")
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

    # Block-based incremental history summarization (see
    # orchestrator/conversation_service.py) — once the raw tail would exceed
    # history_raw_tail_max turns, the oldest history_block_size turns get
    # frozen into a permanent summary, keeping both the raw tail and the
    # per-turn database row bounded regardless of conversation length.
    history_block_size: int = int(os.getenv("HISTORY_BLOCK_SIZE", "10"))
    history_raw_tail_max: int = int(os.getenv("HISTORY_RAW_TAIL_MAX", "15"))

    # How long a session's lock (status='processing' or 'summarizing') is
    # honored before being treated as stale. Kept well above typical turn/
    # summarization latency so this only kicks in when a request/background
    # task has actually crashed or hung.
    freeze_lock_ttl_seconds: int = int(os.getenv("FREEZE_LOCK_TTL_SECONDS", "90"))

    # Per-branch cap for the orchestrator's multi-tool parallel dispatch —
    # bounds how long the whole batch is waited on before proceeding with
    # whatever's ready, rather than letting the slowest branch block the
    # entire reply indefinitely. Kept comfortably below
    # freeze_lock_ttl_seconds so a slow multi-tool turn still finishes well
    # before the processing lock would be considered stale.
    dispatch_branch_timeout_seconds: int = int(os.getenv("DISPATCH_BRANCH_TIMEOUT_SECONDS", "45"))

    # Whether the orchestrator runs its post-answer evaluation step (see
    # orchestrator/evaluation.py) — one extra cheap LLM call per turn (skipped
    # entirely for "general" chat and whenever a tool already signalled
    # needs_clarification) that checks a draft answer actually covers what
    # was asked before it's returned. A kill switch, not a normal per-request
    # knob — useful for isolating cost/latency during load testing.
    enable_answer_evaluation: bool = os.getenv("ENABLE_ANSWER_EVALUATION", "true").lower() == "true"

    # Whether the orchestrator's final-step reply-language conversion runs
    # (see orchestrator/localization.py) — every generation prompt answers
    # in English regardless; this is the one step that, when the user's
    # question wasn't in English, rewrites the finished answer into that
    # language before it's returned. A kill switch, same rationale as
    # enable_answer_evaluation above.
    enable_localization: bool = os.getenv("ENABLE_LOCALIZATION", "true").lower() == "true"

    # Object storage — checklist file uploads. Same Supabase project as
    # conversation_database_url, but a separate API-style credential (a
    # project URL + service_role key, not a Postgres DSN), since Storage is
    # accessed through its own REST API rather than SQL.
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    checklist_storage_bucket: str = os.getenv("CHECKLIST_STORAGE_BUCKET", "checklist-documents")

    # Email verification codes (see app/domains/auth/service.py +
    # app/adapters/resend_email_adapter.py). Unset RESEND_API_KEY makes the
    # adapter print the code to the server log instead of emailing it — a
    # deliberate dev-mode fallback, not an error, so registration is
    # testable without a Resend account.
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    email_from_address: str = os.getenv("EMAIL_FROM_ADDRESS", "onboarding@resend.dev")
    email_verification_ttl_seconds: int = int(os.getenv("EMAIL_VERIFICATION_TTL_SECONDS", "600"))
    email_verification_resend_cooldown_seconds: int = int(
        os.getenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "60")
    )
    email_verification_max_attempts: int = int(os.getenv("EMAIL_VERIFICATION_MAX_ATTEMPTS", "5"))

    # CORS — comma-separated list of allowed frontend origins. Deliberately
    # not "*": that combined with allow_credentials=True isn't a valid CORS
    # response per spec, so browsers make it "work" by reflecting the
    # request's Origin header verbatim — in effect, any origin with
    # credentials. A curated list avoids that.
    cors_allow_origins: str = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )


settings = Settings()

# Fail closed rather than silently signing/verifying tokens with an empty or
# guessable key — an unset JWT_SECRET_KEY would let anyone forge a valid
# token for any user_id. 32 characters is the same floor commonly
# recommended for an HS256 HMAC key.
if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or shorter than 32 characters. Refusing "
        "to start: signing tokens with an empty/weak key lets anyone forge "
        "a valid login for any user. Set JWT_SECRET_KEY in your environment "
        "(see .env) to a long random value, e.g. `python -c \"import secrets; "
        "print(secrets.token_urlsafe(48))\"`."
    )
