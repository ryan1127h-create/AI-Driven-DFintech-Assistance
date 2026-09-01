"""
Contract for a key-value cache with per-key expiry. Anything that needs
cache, session, lock, or blacklist semantics depends on this shape rather
than a specific cache client.
"""

from __future__ import annotations

from typing import Protocol


class CachePort(Protocol):
    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Stores value under key, expiring it after ttl_seconds."""
        ...

    def get(self, key: str) -> str | None:
        """Returns the stored value, or None if the key is absent or
        expired."""
        ...

    def exists(self, key: str) -> bool:
        """True if the key is currently present (and unexpired)."""
        ...

    def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Atomically sets key only if it isn't already present. Returns
        True if this call won (the key is now set to value), False if
        someone else already holds it. Used for distributed locks — the
        atomicity is the entire point, so this can't be built out of
        separate exists()+set() calls."""
        ...

    def delete(self, key: str) -> None:
        """Removes key. A no-op if it wasn't present."""
        ...
