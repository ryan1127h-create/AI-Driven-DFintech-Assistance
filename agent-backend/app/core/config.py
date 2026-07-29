import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    app_name: str = "MSc DFT AI Assistant"
    debug: bool = True

    # Redis — used for chat session storage (see app/core/session_store.py)
    # and for the RAG retrieval result cache (see app/rag/retriever.py)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    # "memory" (default, no Redis required), "redis", or "supabase_cached"
    session_store_backend: str = os.getenv("SESSION_STORE_BACKEND", "memory")

    # Knowledge base — read-only connection to the `Dfintech-agent-db` Supabase
    # project (schema `app`, table `document_chunks`). Only SELECT statements
    # are ever issued against this database (see app/rag/retriever.py).
    knowledge_database_url: str = os.getenv("KNOWLEDGE_DATABASE_URL", "")
    # Used to embed queries at retrieval time — must stay text-embedding-3-small
    # to match the model the knowledge base chunks were embedded with.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # How long a retrieval result stays cached in Redis before being recomputed.
    retrieval_cache_ttl_seconds: int = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "21600"))

    # Conversation storage — independent Supabase project (Phase 2), one row
    # per chat session. Only used once session_store_backend="supabase_cached".
    conversation_database_url: str = os.getenv("CONVERSATION_DATABASE_URL", "")

    # Block-based incremental history summarization (Phase 6) — see
    # app/core/session_store.py::maybe_freeze_block. Once the raw tail would
    # exceed history_raw_tail_max turns, the oldest history_block_size turns
    # get frozen into a permanent summary, keeping both the raw tail and the
    # per-turn database row bounded regardless of conversation length.
    history_block_size: int = int(os.getenv("HISTORY_BLOCK_SIZE", "10"))
    history_raw_tail_max: int = int(os.getenv("HISTORY_RAW_TAIL_MAX", "15"))

settings = Settings()
