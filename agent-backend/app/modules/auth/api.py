from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth import repository, service
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.modules.auth.service import get_current_user_id

router = APIRouter(prefix="/auth")

_bearer_scheme = HTTPBearer(auto_error=True)


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Creates a new account and logs it in immediately (the returned token
    is usable right away — no separate login call required)."""
    try:
        _user, token = service.register(request.email, request.password, request.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        # Full detail stays server-side; clients get a generic message so
        # connection strings/provider errors never leak into responses.
        print(f"[auth.api] Error: registration failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Registration failed.") from exc
    return token


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    try:
        _user, token = service.login(request.email, request.password)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        print(f"[auth.api] Error: login failed — {exc!r}")
        raise HTTPException(status_code=500, detail="Login failed.") from exc
    return token


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    service.logout(credentials.credentials)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user_id: str = Depends(get_current_user_id)):
    row = repository.get_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return service.user_out(row)
