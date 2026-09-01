"""
Shared exception taxonomy. A domain's service layer raises one of these
instead of a bare builtin exception; register_error_handlers() wires each
one to an HTTP status code once, so every domain's api.py gets the same
mapping — and the same "don't leak internal detail to the client" handling
for anything unexpected — for free, instead of each api.py hand-rolling
its own try/except HTTPException translation.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class DomainError(Exception):
    """Base class for errors a domain's service layer raises on purpose —
    an expected outcome of the request, not a bug. See the subclasses
    below for the specific situations each one covers."""


class NotFoundError(DomainError):
    """The requested resource doesn't exist, or doesn't belong to the
    caller — the two are deliberately indistinguishable to the client."""


class ValidationError(DomainError):
    """The request is well-formed JSON/multipart but fails a business rule
    a plain schema check can't express (an unknown checklist item id, an
    unsupported file type, an empty upload, ...)."""


class ConflictError(DomainError):
    """The request can't be satisfied because of something that already
    exists (e.g. an account already registered under this email)."""


class UnauthorizedError(DomainError):
    """Authentication failed, or the presented credentials/token aren't
    valid. Deliberately used for both "wrong password" and "no such
    account" in the auth domain, so the response never reveals which one
    it was."""


class ForbiddenError(DomainError):
    """The caller is authenticated, but the resource they're asking for
    belongs to someone else (e.g. another user's conversation) — distinct
    from UnauthorizedError, where authentication itself is the problem."""


_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ValidationError: 400,
    ConflictError: 409,
    UnauthorizedError: 401,
    ForbiddenError: 403,
}


def register_error_handlers(app: FastAPI) -> None:
    """Wires the taxonomy above into FastAPI. Call once from main.py."""

    for error_type, status_code in _STATUS_BY_ERROR.items():

        def _handler(request: Request, exc: DomainError, _status: int = status_code) -> JSONResponse:
            return JSONResponse(status_code=_status, content={"detail": str(exc)})

        app.add_exception_handler(error_type, _handler)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Full detail stays server-side; the client gets a generic message
        # so connection strings, stack traces, or provider errors never
        # leak into a response.
        logger.exception("unhandled error while processing %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
