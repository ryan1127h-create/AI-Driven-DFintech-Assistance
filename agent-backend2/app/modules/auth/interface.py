"""
Public interface of the auth module — the ONLY file other modules are
allowed to import from app.modules.auth. Everything else in this package
(repository, security, service internals) is private to this module.

Current consumers:
    - every other module's api.py uses get_current_user_id as a FastAPI
      dependency to resolve the calling user_id from the request's JWT.

Usage (see e.g. app/modules/profile/api.py):
    from app.modules.auth.interface import get_current_user_id

    @router.get("", response_model=ProfileOut)
    async def get_profile(user_id: str = Depends(get_current_user_id)):
        ...
"""

from __future__ import annotations

from app.modules.auth.service import get_current_user_id

__all__ = ["get_current_user_id"]
