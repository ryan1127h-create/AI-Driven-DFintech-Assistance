"""
Singleton Redis connection, shared by any component that needs Redis
(currently session storage; future candidates: rate limiting, response caching).
"""

import redis

from app.core.config import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def ping() -> bool:
    """Returns True if Redis is reachable, False otherwise (never raises)."""
    try:
        return bool(get_redis_client().ping())
    except redis.exceptions.RedisError:
        return False
