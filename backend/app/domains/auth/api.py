from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import NotFoundError
from app.domains.auth import repository, service
from app.domains.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.domains.auth.service import get_current_user_id

router = APIRouter(prefix="/auth")

_bearer_scheme = HTTPBearer(auto_error=True)


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Creates a new account and logs it in immediately — the returned
    token is usable right away, no separate login call required."""
    _user, token = service.register(request.email, request.password, request.full_name)
    return token


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    _user, token = service.login(request.email, request.password)
    return token


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    service.logout(credentials.credentials)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user_id: str = Depends(get_current_user_id)):
    row = repository.get_by_id(user_id)
    if row is None:
        raise NotFoundError("User not found.")
    return service.user_out(row)
