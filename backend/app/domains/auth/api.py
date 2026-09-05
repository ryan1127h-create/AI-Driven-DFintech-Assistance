from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import NotFoundError
from app.domains.auth import repository, service
from app.domains.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RegistrationStartedResponse,
    ResendCodeRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.domains.auth.service import get_current_user_id

router = APIRouter(prefix="/auth")

_bearer_scheme = HTTPBearer(auto_error=True)


@router.post("/register", response_model=RegistrationStartedResponse)
async def register(request: RegisterRequest):
    """Starts registration: validates the email against the chosen role
    (enrolled_student requires an @u.nus.edu address) and emails a 6-digit
    verification code. No account exists yet — call /auth/verify-email with
    the code to actually create it and get a usable token."""
    return service.start_registration(request.email, request.password, request.full_name, request.role)


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(request: VerifyEmailRequest):
    """Completes registration and logs the new account in immediately —
    the returned token is usable right away, no separate login call
    required."""
    return service.verify_email(request.email, request.code)


@router.post("/resend-code", response_model=RegistrationStartedResponse)
async def resend_code(request: ResendCodeRequest):
    return service.resend_code(request.email)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    return service.login(request.email, request.password, request.role)


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
