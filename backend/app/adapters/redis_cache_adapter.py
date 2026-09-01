"""
Redis adapter for CachePort. A connection/command failure is allowed to
raise rather than being swallowed here — callers that want fail-open
behavior for a specific operation (e.g. auth's blacklist check, where a
Redis outage shouldn't lock every user out) catch it themselves, since not
every caller wants the same degradation policy.
"""

from __future__ import annotations

import redis

from app.core.config import settings
from app.ports.cache_port import CachePort


class RedisCacheAdapter(CachePort):
    def __init__(self, redis_url: str) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        return bool(self._client.set(key, value, nx=True, ex=ttl_seconds))

    def delete(self, key: str) -> None:
        self._client.delete(key)


cache = RedisCacheAdapter(settings.redis_url)
