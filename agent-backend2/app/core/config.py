import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Kimi (Moonshot AI) — OpenAI-API-compatible chat completion backend used
    # by every LLM call in the app (see app/clients/kimi_client.py). Kimi's
    # current model lineup only accepts temperature=1, so the client always
    # sends temperature=1 regardless of what callers request.
    kimi_api_key: str = os.getenv("KIMI_API_KEY", "")
    kimi_base_url: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    # kimi-k2.7-code-highspeed measured ~4-5x faster than kimi-k2.6 for the
    # same prompts (lower reasoning-token overhead), with comparable answer
    # quality/tone in testing — chosen as the latency-sensitive default.
    kimi_model: str = os.getenv("KIMI_MODEL", "kimi-k2.7-code-highspeed")
    app_name: str = "MSc DFT AI Assistant"
    debug: bool = True

    # Redis — used for chat session storage (see
    # app/modules/chatbot/repository.py) and for the RAG retrieval result
    # cache (see app/services/rag_service.py)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    # "memory" (default, no Redis required), "redis", or "supabase_cached"
    session_store_backend: str = os.getenv("SESSION_STORE_BACKEND", "memory")

    # Knowledge base — read-only connection to the `Dfintech-agent-db` Supabase
    # project (schema `app`, table `document_chunks`). Only SELECT statements
    # are ever issued against this database (see
    # app/repositories/knowledge_repository.py).
    knowledge_database_url: str = os.getenv("KNOWLEDGE_DATABASE_URL", "")
    # Used to embed queries at retrieval time — must stay text-embedding-3-small
    # to match the model the knowledge base chunks were embedded with.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # How long a retrieval result stays cached in Redis before being recomputed.
    retrieval_cache_ttl_seconds: int = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "21600"))

    # Conversation storage — independent Supabase project (Phase 2), one row
    # per chat session. Only used once session_store_backend="supabase_cached".
    conversation_database_url: str = os.getenv("CONVERSATION_DATABASE_URL", "")

    # Block-based incremental history summarization — see
    # app/modules/chatbot/conversation_service.py::should_freeze. Once the
    # raw tail would exceed history_raw_tail_max turns, the oldest
    # history_block_size turns get frozen into a permanent summary, keeping
    # both the raw tail and the per-turn database row bounded regardless of
    # conversation length.
    history_block_size: int = int(os.getenv("HISTORY_BLOCK_SIZE", "10"))
    history_raw_tail_max: int = int(os.getenv("HISTORY_RAW_TAIL_MAX", "15"))

    # How long a session's lock (status='processing' or 'summarizing') is
    # honored before being treated as stale — see
    # app/modules/chatbot/repository.py::ConversationStore.try_lock. Set
    # well above typical turn/summarization latency so this only kicks in
    # when a request/background task has actually crashed/hung, not during
    # normal operation. Originally 60s (observed ~5-15s pre-integration);
    # raised to leave headroom above dispatch_branch_timeout_seconds now
    # that career/comparison turns can trigger several sequential LLM calls
    # (career_planning/program_comparison integration — see
    # app/modules/chatbot/agents/specialists/career.py, comparison.py).
    # Re-measure real p95/p99 turn latency once deployed and adjust.
    freeze_lock_ttl_seconds: int = int(os.getenv("FREEZE_LOCK_TTL_SECONDS", "90"))

    # Per-branch cap for dispatch_node's multi-intent parallel fan-out (see
    # app/modules/chatbot/agents/supervisor.py::dispatch_node) — bounds how
    # long the whole batch of parallel specialist calls is waited on before
    # proceeding with whatever's ready, rather than letting the slowest
    # branch (career/comparison can now involve several sequential LLM
    # calls) block the entire reply indefinitely. Kept comfortably below
    # freeze_lock_ttl_seconds so a slow multi-intent turn still finishes
    # well before the processing lock would be considered stale.
    dispatch_branch_timeout_seconds: int = int(os.getenv("DISPATCH_BRANCH_TIMEOUT_SECONDS", "45"))

    # Supabase Storage — object storage for checklist file uploads (see
    # app/clients/storage_client.py and app/modules/checklist/service.py).
    # Separate credentials from CONVERSATION_DATABASE_URL: that's a direct
    # Postgres DSN, this is the project's API URL + service_role key (from
    # Supabase dashboard > Project Settings > API), needed to call the
    # Storage REST API. Same Supabase project as CONVERSATION_DATABASE_URL.
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    checklist_storage_bucket: str = os.getenv("CHECKLIST_STORAGE_BUCKET", "checklist-documents")

    # Auth — self-issued JWT access tokens (see app/modules/auth/security.py).
    # Signing algorithm is fixed at HS256, not env-configurable — there's no
    # reason for this project to vary it, same reasoning as
    # app/clients/openai_client.py::EMBED_MODEL being a fixed constant.
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_access_token_expire_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))  # 7 days
    )

    # CORS — comma-separated list of allowed frontend origins. Defaults to
    # the common local dev ports (CRA/Next/Vite) rather than "*": a wildcard
    # combined with allow_credentials=True (see app/main.py) isn't a valid
    # CORS response per spec, so browsers make it work by reflecting the
    # request's Origin header verbatim — in practice "any origin, with
    # credentials" is allowed, which is broader than a plain wildcard.
    # Override with the real frontend origin(s) once one exists.
    cors_allow_origins: str = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )

settings = Settings()

# Fail closed rather than silently signing/verifying tokens with an empty or
# guessable key — an unset JWT_SECRET_KEY would otherwise let anyone forge a
# token for any user_id (see app/modules/auth/security.py). 32 chars is the
# same floor commonly recommended for an HS256 HMAC key.
if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or shorter than 32 characters. Refusing to "
        "start: signing tokens with an empty/weak key lets anyone forge a "
        "valid login for any user. Set JWT_SECRET_KEY in your environment "
        "(see .env) to a long random value, e.g. `python -c \"import secrets; "
        "print(secrets.token_urlsafe(48))\"`."
    )
