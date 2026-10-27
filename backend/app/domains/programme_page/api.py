from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import UnauthorizedError
from app.domains.auth.interface import get_current_user_id
from app.domains.programme_page import service

router = APIRouter(prefix="/programme")

# The page is public: a missing or expired token just means a visitor.
_optional_bearer = HTTPBearer(auto_error=False)


def _signed_in(credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer)) -> bool:
    if credentials is None:
        return False
    try:
        get_current_user_id(credentials)
    except UnauthorizedError:
        return False
    return True


@router.get("/overview")
def get_programme_overview(signed_in: bool = Depends(_signed_in)):
    """MSc DFT at a glance, for anyone: facts, curriculum, admissions,
    fees, careers and alumni stories (named only for signed-in readers)."""
    return service.get_page(signed_in)
