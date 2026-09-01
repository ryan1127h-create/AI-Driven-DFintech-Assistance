"""
Public interface of the auth domain — the only module other domains (and
the orchestrator) are allowed to import from app.domains.auth.
Everything else in this package (repository, security, service internals)
is private.

Usage:
    from app.domains.auth.interface import get_current_user_id

    @router.get("", response_model=ProfileOut)
    async def get_profile(user_id: str = Depends(get_current_user_id)):
        ...
"""

from __future__ import annotations

from app.domains.auth.service import get_current_user_id

__all__ = ["get_current_user_id"]
