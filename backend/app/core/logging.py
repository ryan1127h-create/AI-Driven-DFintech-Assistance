"""
Structured logging with a per-request correlation id. Every log line
emitted through get_logger() carries whichever correlation id is bound for
the current request (or "-" outside of one), so the lines belonging to a
single request can be grepped together even while other requests are being
handled concurrently.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class _CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Call once at process startup. Safe to call more than once — if a
    handler is already attached, later calls are no-ops, so a module that
    triggers this twice (e.g. under pytest) doesn't duplicate log lines."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(_CorrelationIdFilter())
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_correlation_id() -> str:
    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation id to every incoming request — reusing the
    `X-Correlation-ID` request header when the caller supplies one (so an
    id generated upstream, e.g. by the frontend, survives into backend
    logs), otherwise minting a fresh one — and echoes it back on the
    response so a client can quote it when reporting an issue."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or uuid.uuid4().hex
        token = _correlation_id.set(correlation_id)
        try:
            response: Response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
