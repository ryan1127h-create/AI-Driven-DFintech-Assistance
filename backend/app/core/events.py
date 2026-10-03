"""
A minimal in-process event hook, so a lower layer can say "this user's
profile changed" without importing whoever reacts to it (the derived
labels sit above the profile domain they read). Handlers run on a small
background pool, never on the request, and a failing handler is only
logged.

    events.subscribe(events.PROFILE_CHANGED, recompute)   # at startup
    events.publish(events.PROFILE_CHANGED, user_id)       # after a write
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

# The user's profile facts changed (answers, school-record stage, ...).
PROFILE_CHANGED = "profile_changed"
# The user came back (login / session refresh): time-based labels may be stale.
USER_SEEN = "user_seen"

_handlers: dict[str, list[Callable[[str], None]]] = defaultdict(list)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="events")


def subscribe(event: str, handler: Callable[[str], None]) -> None:
    if handler not in _handlers[event]:
        _handlers[event].append(handler)


def _run(event: str, handler: Callable[[str], None], user_id: str) -> None:
    try:
        handler(user_id)
    except Exception as exc:
        logger.warning("%s handler %s failed for %s: %r", event, getattr(handler, "__name__", handler), user_id, exc)


def publish(event: str, user_id: str) -> None:
    for handler in list(_handlers.get(event, ())):
        _pool.submit(_run, event, handler, user_id)
