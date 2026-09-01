"""
Generic timeout/retry helpers for anything that calls out to a slow or
unreliable dependency (an LLM, a downstream HTTP call, a tool handler).
Kept dependency-free — plain threads and time.sleep, no external retry
library — since the whole surface needed here is "run this, give up after
N seconds, optionally try again."
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


class TimeoutExceeded(Exception):
    """Raised when a call did not finish within its allotted time."""


_executor = ThreadPoolExecutor(thread_name_prefix="resilience")


def run_with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    """Runs a blocking callable on a worker thread and enforces a
    wall-clock timeout. Useful for bounding calls whose own client library
    has no timeout knob, or whose knob doesn't cover every failure mode
    (e.g. a connection that hangs instead of erroring)."""
    future = _executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except _FutureTimeoutError as exc:
        raise TimeoutExceeded(f"call exceeded {timeout_seconds}s") from exc


def retry(fn: Callable[[], T], *, attempts: int = 3, backoff_seconds: float = 0.5) -> T:
    """Retries a blocking callable up to `attempts` times with linear
    backoff. Only worth wrapping a call in this when its failures are
    transient (rate limits, brief network blips) — a call that fails
    deterministically (bad input, a 4xx) will just fail the same way
    `attempts` times, wasting the backoff delay for nothing."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            last_exc = exc
            if attempt < attempts:
                time.sleep(backoff_seconds * attempt)
    assert last_exc is not None
    raise last_exc
