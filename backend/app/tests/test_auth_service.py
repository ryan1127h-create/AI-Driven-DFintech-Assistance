"""Exercises domains/auth/service.py's registration flow: role/email-domain
validation, applicants registered immediately without verification, the
enrolled-student register-then-verify handoff through Redis (never
creating an account until verification succeeds), resend cooldown, the
wrong-code attempt cap, that a failed email send never leaves behind a
pending entry that looks like it succeeded, the registration role recorded
as the profile's lifecycle_stage, and login's derived-role and
disabled-account checks — on top of a fake AuthPort standing in for
Supabase Auth and in-memory stand-ins for the account and profile stores."""

from __future__ import annotations

import json

import pytest

from app.core.errors import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.domains.auth import service
from app.ports.auth_port import AuthenticationError, AuthSession


class _FakeCache:
    """Minimal in-memory stand-in for CachePort — enough for service.py's
    get/set/delete/exists usage, no real Redis needed for these tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    def exists(self, key: str) -> bool:
        return key in self._store

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _FakeEmail:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, text_body: str) -> None:
        if self.fail:
            raise RuntimeError("delivery failed")
        self.sent.append((to, subject, text_body))


class _FakeAccounts:
    """Stand-in for the account.accounts rows the auth.users trigger
    creates, plus each user's profile lifecycle_stage and consents."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.stages: dict[str, str] = {}
        self.consents: dict[str, dict[str, bool]] = {}
        self.fail_stage_write = False
        self.last_login: list[str] = []
        self.onboarding: dict[str, str] = {}

    def add(self, user_id: str, email: str, full_name: str = "Test User") -> None:
        self.rows[user_id] = {
            "user_id": user_id, "email": email, "full_name": full_name,
            "role": "user", "account_status": "active",
        }

    def by_email(self, email: str) -> dict | None:
        return next((r for r in self.rows.values() if r["email"] == email), None)

    def set_stage(self, user_id: str, stage: str, *, source: str, actor: str) -> None:
        if self.fail_stage_write:
            raise RuntimeError("profile store down")
        assert (source, actor) == ("QA", f"user:{user_id}")
        self.stages[user_id] = stage

    def set_full_name(self, user_id: str, full_name: str) -> bool:
        if user_id not in self.rows:
            return False
        self.rows[user_id]["full_name"] = full_name
        return True

    def set_onboarding(self, user_id: str, status: str) -> bool:
        if user_id not in self.rows:
            return False
        self.onboarding[user_id] = status
        return True

    def record_consents(self, user_id: str, decisions: dict[str, bool]) -> None:
        self.consents.setdefault(user_id, {}).update(decisions)


class _FakeAuthProvider:
    """Stand-in for AuthPort/SupabaseAuthAdapter — an in-memory
    email/password->user_id store, enough to exercise service.py's
    create-then-sign-in and sign-in-only (login) paths without a real
    Supabase project. Creating a user also creates its account row, as the
    auth.users trigger does in the real database."""

    def __init__(self, accounts: _FakeAccounts) -> None:
        self.names: dict[str, str] = {}
        self.fail_name_update = False
        self.created_users: list[tuple[str, str, str]] = []
        self.deleted: list[str] = []
        self._accounts: dict[str, tuple[str, str]] = {}  # email -> (user_id, password)
        self._next_id = 0
        self._account_store = accounts

    def create_user(self, email: str, password: str, full_name: str) -> str:
        self._next_id += 1
        user_id = f"11111111-1111-1111-1111-{self._next_id:012d}"
        self.created_users.append((email, password, full_name))
        self._accounts[email] = (user_id, password)
        self._account_store.add(user_id, email, full_name)
        return user_id

    def sign_in(self, email: str, password: str) -> AuthSession:
        entry = self._accounts.get(email)
        if entry is None or entry[1] != password:
            raise AuthenticationError("Invalid login credentials.")
        user_id, _ = entry
        return AuthSession(user_id=user_id, access_token=f"token-for-{user_id}", expires_in=3600)

    def update_full_name(self, user_id: str, full_name: str) -> None:
        if self.fail_name_update:
            raise RuntimeError("supabase down")
        self.names[user_id] = full_name

    def delete_user(self, user_id: str) -> None:
        # The real cascade: deleting the provider's user removes the account.
        self.deleted.append(user_id)
        self._account_store.rows.pop(user_id, None)

    def sign_out(self, access_token: str) -> None:
        pass


@pytest.fixture()
def fake_cache(monkeypatch):
    fake = _FakeCache()
    monkeypatch.setattr(service, "cache", fake)
    return fake


@pytest.fixture()
def fake_email(monkeypatch):
    fake = _FakeEmail()
    monkeypatch.setattr(service, "email_sender", fake)
    return fake


@pytest.fixture(autouse=True)
def accounts(monkeypatch):
    """No test touches a real database: account reads and the profile's
    lifecycle_stage go through this in-memory store."""
    fake = _FakeAccounts()
    monkeypatch.setattr(service.repository, "get_account", lambda uid: fake.rows.get(uid))
    monkeypatch.setattr(service.repository, "get_account_by_email", fake.by_email)
    monkeypatch.setattr(service.repository, "touch_last_login", fake.last_login.append)
    monkeypatch.setattr(service.profile_interface, "set_lifecycle_stage", fake.set_stage)
    monkeypatch.setattr(service.profile_interface, "record_consents", fake.record_consents)
    monkeypatch.setattr(service.profile_interface, "get_profile_field", lambda uid, key: fake.stages.get(uid))
    monkeypatch.setattr(service.repository, "get_onboarding_status",
                        lambda uid: fake.onboarding.get(uid, "not_started") if uid in fake.rows else None)
    monkeypatch.setattr(service.repository, "set_onboarding_status", fake.set_onboarding)
    monkeypatch.setattr(service.repository, "set_full_name", fake.set_full_name)
    return fake


@pytest.fixture()
def fake_auth_provider(monkeypatch, accounts):
    fake = _FakeAuthProvider(accounts)
    monkeypatch.setattr(service, "auth_provider", fake)
    return fake


NUS_EMAIL = "e0000001@u.nus.edu"


def _extract_code(fake_email: _FakeEmail) -> str:
    body = fake_email.sent[-1][2]
    # "Your NUS DFT verification code is 123456.\n\n..."
    return body.split("code is ")[1].split(".")[0]


def _start_enrolled(consent: bool = False):
    return service.start_registration(
        NUS_EMAIL, "password123", "Test Student", "enrolled_student", consent_personalized_rec=consent
    )


def _expire_cooldown(fake_cache: _FakeCache) -> None:
    blob = json.loads(fake_cache.get(service._pending_key(NUS_EMAIL)))
    blob["last_sent_at"] = 0
    fake_cache.set(service._pending_key(NUS_EMAIL), json.dumps(blob), ttl_seconds=600)


# ---- role derivation --------------------------------------------------------

@pytest.mark.parametrize("account_role, stage, expected", [
    ("admin", None, "admin"),
    ("admin", "current", "admin"),
    ("user", "current", "enrolled_student"),
    ("user", "graduating", "enrolled_student"),
    ("user", "alumni", "enrolled_student"),
    ("user", "admitted", "applicant"),
    ("user", "prospect", "applicant"),
    ("user", None, "applicant"),
])
def test_derive_role(account_role, stage, expected):
    assert service.derive_role(account_role, stage) == expected


# ---- registration: applicant ------------------------------------------------

def test_applicant_is_registered_and_logged_in_without_verification(fake_cache, fake_email, fake_auth_provider, accounts):
    response = service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")

    assert response.access_token
    assert response.user.email == "someone@gmail.com"
    assert response.user.role == "applicant"
    assert response.user.lifecycle_stage == "prospect"
    assert accounts.stages[response.user.user_id] == "prospect"
    assert accounts.consents[response.user.user_id] == {"consent_personalized_rec": False}
    assert fake_auth_provider.created_users == [("someone@gmail.com", "password123", "Test Applicant")]
    assert fake_email.sent == []
    assert service._load_pending("someone@gmail.com") is None


def test_registration_records_the_consent_choice(fake_cache, fake_email, fake_auth_provider, accounts):
    response = service.start_registration(
        "someone@gmail.com", "password123", "Test Applicant", "applicant", consent_personalized_rec=True
    )
    assert accounts.consents[response.user.user_id] == {"consent_personalized_rec": True}


def test_applicant_account_survives_a_failed_stage_write(fake_cache, fake_email, fake_auth_provider, accounts):
    accounts.fail_stage_write = True
    response = service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    assert response.access_token
    assert response.user.role == "applicant"
    assert response.user.lifecycle_stage is None


def test_register_rejects_an_already_registered_email(fake_cache, fake_email, accounts):
    accounts.add("u1", NUS_EMAIL)
    with pytest.raises(ConflictError):
        _start_enrolled()
    accounts.add("u2", "existing@gmail.com")
    with pytest.raises(ConflictError):
        service.start_registration("existing@gmail.com", "password123", "Existing", "applicant")


# ---- registration: enrolled student -----------------------------------------

def test_enrolled_student_requires_nus_email(fake_cache, fake_email):
    with pytest.raises(ValidationError):
        service.start_registration("someone@gmail.com", "password123", "Test Student", "enrolled_student")
    assert fake_email.sent == []


def test_enrolled_student_is_only_emailed_a_code(fake_cache, fake_email, fake_auth_provider):
    result = _start_enrolled()
    assert result.email == NUS_EMAIL
    assert len(fake_email.sent) == 1
    assert fake_auth_provider.created_users == []


def test_failed_email_send_raises_a_clear_error_and_leaves_no_pending_entry(fake_cache, monkeypatch):
    failing_email = _FakeEmail(fail=True)
    monkeypatch.setattr(service, "email_sender", failing_email)

    # The adapter's own exception (RuntimeError here) is translated into a
    # ServiceUnavailableError, not left to propagate raw — see
    # backend/app/core/errors.py's taxonomy and register_error_handlers(),
    # which maps this to a 503 with a message the frontend can show
    # directly, instead of FastAPI's generic 500 "Internal server error."
    with pytest.raises(ServiceUnavailableError):
        _start_enrolled()

    # A legitimate retry right after must NOT be blocked by a resend
    # cooldown — there is nothing pending to have a cooldown on.
    assert service._load_pending(NUS_EMAIL) is None


def test_resend_code_also_translates_a_failed_send(fake_cache, fake_email):
    _start_enrolled()
    _expire_cooldown(fake_cache)

    fake_email.fail = True
    with pytest.raises(ServiceUnavailableError):
        service.resend_code(NUS_EMAIL)


def test_resend_cooldown_blocks_a_second_register_call(fake_cache, fake_email):
    _start_enrolled()
    with pytest.raises(RateLimitError):
        _start_enrolled()
    assert len(fake_email.sent) == 1  # the second attempt never sent another email


def test_resend_code_reuses_the_original_signup_details(fake_cache, fake_email):
    _start_enrolled()
    _expire_cooldown(fake_cache)

    service.resend_code(NUS_EMAIL)
    assert len(fake_email.sent) == 2
    assert fake_email.sent[1][0] == NUS_EMAIL


def test_resend_code_is_silent_about_unknown_emails(fake_cache, fake_email):
    result = service.resend_code("never-registered@gmail.com")
    assert result.email == "never-registered@gmail.com"
    assert fake_email.sent == []  # nothing to resend, but no error either


def test_verify_email_wrong_code_does_not_extend_the_window(fake_cache, fake_email):
    _start_enrolled()
    original_created_at = service._load_pending(NUS_EMAIL)["created_at"]

    with pytest.raises(ValidationError):
        service.verify_email(NUS_EMAIL, "000000")

    pending = service._load_pending(NUS_EMAIL)
    assert pending["attempts"] == 1
    assert pending["created_at"] == original_created_at  # window didn't reset


def test_verify_email_caps_attempts(fake_cache, fake_email, monkeypatch):
    monkeypatch.setattr(service.settings, "email_verification_max_attempts", 2)
    _start_enrolled()

    with pytest.raises(ValidationError):
        service.verify_email(NUS_EMAIL, "000000")
    with pytest.raises(ValidationError):
        service.verify_email(NUS_EMAIL, "111111")
    with pytest.raises(RateLimitError):
        service.verify_email(NUS_EMAIL, "222222")

    assert service._load_pending(NUS_EMAIL) is None  # cleaned up after the cap


def test_verify_email_success_creates_the_user_and_logs_in(fake_cache, fake_email, fake_auth_provider, accounts):
    _start_enrolled(consent=True)
    code = _extract_code(fake_email)

    response = service.verify_email(NUS_EMAIL, code)
    assert response.user.email == NUS_EMAIL
    assert response.user.role == "enrolled_student"
    assert response.user.lifecycle_stage == "current"
    assert response.access_token
    assert fake_auth_provider.created_users == [(NUS_EMAIL, "password123", "Test Student")]
    assert accounts.stages[response.user.user_id] == "current"
    # The consent choice made when registering survives the verification wait.
    assert accounts.consents[response.user.user_id] == {"consent_personalized_rec": True}
    # One-time use: the pending entry is gone, a second verify fails.
    with pytest.raises(ValidationError):
        service.verify_email(NUS_EMAIL, code)


def test_verify_email_with_no_pending_registration(fake_cache, fake_email):
    with pytest.raises(ValidationError):
        service.verify_email("never-registered@gmail.com", "123456")


# ---- login: the derived role must match the portal picked -------------------

def _registered(fake_auth_provider, accounts, *, role="user", stage=None, status="active") -> str:
    user_id = fake_auth_provider.create_user("someone@gmail.com", "password123", "Test User")
    accounts.rows[user_id].update(role=role, account_status=status)
    if stage:
        accounts.stages[user_id] = stage
    return user_id


def test_login_succeeds_when_selected_role_matches(fake_auth_provider, accounts):
    user_id = _registered(fake_auth_provider, accounts, stage="applicant")

    response = service.login("someone@gmail.com", "password123", "applicant")
    assert response.user.role == "applicant"
    assert response.user.user_id == user_id
    assert accounts.last_login == [user_id]


def test_login_as_enrolled_student_follows_lifecycle_stage(fake_auth_provider, accounts):
    _registered(fake_auth_provider, accounts, stage="current")
    assert service.login("someone@gmail.com", "password123", "enrolled_student").user.role == "enrolled_student"
    with pytest.raises(UnauthorizedError):
        service.login("someone@gmail.com", "password123", "applicant")


def test_login_as_admin(fake_auth_provider, accounts):
    _registered(fake_auth_provider, accounts, role="admin")
    assert service.login("someone@gmail.com", "password123", "admin").user.role == "admin"


def test_login_rejects_a_mismatched_role_even_with_the_correct_password(fake_auth_provider, accounts):
    _registered(fake_auth_provider, accounts, stage="applicant")
    with pytest.raises(UnauthorizedError):
        service.login("someone@gmail.com", "password123", "admin")
    assert accounts.last_login == []


def test_login_rejects_a_disabled_account(fake_auth_provider, accounts):
    _registered(fake_auth_provider, accounts, stage="applicant", status="disabled")
    with pytest.raises(UnauthorizedError, match="disabled"):
        service.login("someone@gmail.com", "password123", "applicant")


def test_login_wrong_password_is_checked_before_role(fake_auth_provider, accounts):
    _registered(fake_auth_provider, accounts)
    with pytest.raises(UnauthorizedError):
        service.login("someone@gmail.com", "wrong-password", "admin")


def test_login_unknown_email_is_rejected(fake_auth_provider):
    with pytest.raises(UnauthorizedError):
        service.login("never-registered@gmail.com", "password123", "applicant")


def test_new_accounts_start_onboarding_and_can_finish_it(fake_cache, fake_email, fake_auth_provider, accounts):
    response = service.start_registration("someone@gmail.com", "password123", "Some One", "applicant", False)
    assert response.user.onboarding_status == "not_started"
    assert service.set_onboarding_status(response.user.user_id, "completed").onboarding_status == "completed"


def test_onboarding_status_of_a_missing_account_is_not_found(accounts):
    with pytest.raises(NotFoundError):
        service.set_onboarding_status("nobody", "skipped")


@pytest.mark.parametrize("provider_fails", [False, True])
def test_renaming_updates_the_account_even_if_the_provider_copy_fails(
    fake_cache, fake_email, fake_auth_provider, accounts, provider_fails,
):
    user_id = service.start_registration("someone@gmail.com", "password123", "Some One", "applicant", False).user.user_id
    fake_auth_provider.fail_name_update = provider_fails
    assert service.update_full_name(user_id, "Someone Else").full_name == "Someone Else"
    assert fake_auth_provider.names.get(user_id) == (None if provider_fails else "Someone Else")


def test_deleting_an_account_deletes_the_provider_user(fake_cache, fake_email, fake_auth_provider, accounts):
    user_id = service.start_registration("someone@gmail.com", "password123", "Some One", "applicant", False).user.user_id
    service.delete_account(user_id)
    assert fake_auth_provider.deleted == [user_id]
    assert user_id not in accounts.rows


def test_deleting_a_missing_account_is_not_found(fake_auth_provider):
    with pytest.raises(NotFoundError):
        service.delete_account("nobody")
    assert fake_auth_provider.deleted == []


def test_account_names_are_trimmed_and_not_blank():
    from pydantic import ValidationError as PydanticValidationError

    from app.domains.auth.schemas import AccountUpdate

    assert AccountUpdate(full_name="  Jane   Tan ").full_name == "Jane Tan"
    with pytest.raises(PydanticValidationError):
        AccountUpdate(full_name="   ")

