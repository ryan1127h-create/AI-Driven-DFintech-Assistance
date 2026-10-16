from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import events
from app.core.errors import NotFoundError
from app.domains.auth import service
from app.domains.auth.schemas import (
    AccountUpdate,
    AuthResponse,
    LoginRequest,
    OnboardingUpdate,
    SettingsOut,
    SettingsUpdate,
    RegisterRequest,
    RegistrationStartedResponse,
    ResendCodeRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.domains.auth.service import get_current_user_id

router = APIRouter(prefix="/auth")

_bearer_scheme = HTTPBearer(auto_error=True)


@router.post("/register", response_model=AuthResponse | RegistrationStartedResponse)
def register(request: RegisterRequest):
    """An applicant (any email) is registered and logged in immediately —
    the response is an AuthResponse with a usable token. An enrolled
    student (@u.nus.edu address required) is instead emailed a 6-digit
    verification code and no account exists yet — call /auth/verify-email
    with the code to actually create it and get a usable token."""
    return service.start_registration(
        request.email, request.password, request.full_name, request.role, request.consent_personalized_rec
    )


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(request: VerifyEmailRequest):
    """Completes registration and logs the new account in immediately —
    the returned token is usable right away, no separate login call
    required."""
    return service.verify_email(request.email, request.code)


@router.post("/resend-code", response_model=RegistrationStartedResponse)
def resend_code(request: ResendCodeRequest):
    return service.resend_code(request.email)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    return service.login(request.email, request.password, request.role)


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    service.logout(credentials.credentials)
    return {"status": "logged_out"}


@router.patch("/me", response_model=UserOut)
def update_me(request: AccountUpdate, user_id: str = Depends(get_current_user_id)):
    """Changes the caller's display name."""
    return service.update_full_name(user_id, request.full_name)


@router.get("/me", response_model=UserOut)
def me(user_id: str = Depends(get_current_user_id)):
    user = service.get_user(user_id)
    if user is None:
        raise NotFoundError("User not found.")
    # The app calls this on every start: a cue to refresh time-based labels.
    events.publish(events.USER_SEEN, user_id)
    return user


@router.put("/onboarding", response_model=UserOut)
def set_onboarding(request: OnboardingUpdate, user_id: str = Depends(get_current_user_id)):
    """Records that the caller skipped or finished the profile welcome
    questionnaire; returns the refreshed user."""
    return service.set_onboarding_status(user_id, request.status)


@router.get("/settings", response_model=SettingsOut)
def get_settings(user_id: str = Depends(get_current_user_id)):
    """The caller's assistant preferences."""
    return service.get_settings(user_id)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(request: SettingsUpdate, user_id: str = Depends(get_current_user_id)):
    """Changes the settings given; returns all of them."""
    return service.update_settings(user_id, request.model_dump(exclude_none=True))
