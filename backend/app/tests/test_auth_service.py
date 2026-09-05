"""Exercises domains/auth/service.py's registration flow: role/email-domain
validation, the two-step register-then-verify handoff through Redis (never
touching student.users until verification succeeds), resend cooldown, the
wrong-code attempt cap, and that a failed email send never leaves behind a
pending entry that looks like it succeeded."""

from __future__ import annotations

import time

import pytest

from app.core.errors import ConflictError, RateLimitError, ServiceUnavailableError, UnauthorizedError, ValidationError
from app.domains.auth import service


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
def no_repository_hits(monkeypatch):
    """None of these tests should touch a real database — get_by_email
    defaults to "no existing account" unless a test overrides it."""
    monkeypatch.setattr(service.repository, "get_by_email", lambda email: None)


def _extract_code(fake_email: _FakeEmail) -> str:
    body = fake_email.sent[-1][2]
    # "Your NUS DFT verification code is 123456.\n\n..."
    return body.split("code is ")[1].split(".")[0]


def test_enrolled_student_requires_nus_email(fake_cache, fake_email):
    with pytest.raises(ValidationError):
        service.start_registration("someone@gmail.com", "password123", "Test Student", "enrolled_student")
    assert fake_email.sent == []


def test_applicant_accepts_any_email(fake_cache, fake_email):
    result = service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    assert result.email == "someone@gmail.com"
    assert len(fake_email.sent) == 1


def test_register_rejects_an_already_registered_email(monkeypatch, fake_cache, fake_email):
    monkeypatch.setattr(service.repository, "get_by_email", lambda email: {"user_id": "u1"})
    with pytest.raises(ConflictError):
        service.start_registration("existing@u.nus.edu", "password123", "Existing", "enrolled_student")


def test_failed_email_send_raises_a_clear_error_and_leaves_no_pending_entry(fake_cache, monkeypatch):
    failing_email = _FakeEmail(fail=True)
    monkeypatch.setattr(service, "email_sender", failing_email)

    # The adapter's own exception (RuntimeError here) is translated into a
    # ServiceUnavailableError, not left to propagate raw — see
    # backend/app/core/errors.py's taxonomy and register_error_handlers(),
    # which maps this to a 503 with a message the frontend can show
    # directly, instead of FastAPI's generic 500 "Internal server error."
    with pytest.raises(ServiceUnavailableError):
        service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")

    # A legitimate retry right after must NOT be blocked by a resend
    # cooldown — there is nothing pending to have a cooldown on.
    assert service._load_pending("someone@gmail.com") is None


def test_resend_code_also_translates_a_failed_send(fake_cache, fake_email):
    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    pending = fake_cache.get(service._pending_key("someone@gmail.com"))
    import json
    blob = json.loads(pending)
    blob["last_sent_at"] = 0  # bypass the resend cooldown for this test
    fake_cache.set(service._pending_key("someone@gmail.com"), json.dumps(blob), ttl_seconds=600)

    fake_email.fail = True
    with pytest.raises(ServiceUnavailableError):
        service.resend_code("someone@gmail.com")


def test_resend_cooldown_blocks_a_second_register_call(fake_cache, fake_email):
    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    with pytest.raises(RateLimitError):
        service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    assert len(fake_email.sent) == 1  # the second attempt never sent another email


def test_resend_code_reuses_the_original_signup_details(fake_cache, fake_email):
    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    pending = fake_cache.get(service._pending_key("someone@gmail.com"))
    assert pending is not None

    # Manually expire the cooldown so resend is allowed in this test.
    import json
    blob = json.loads(pending)
    blob["last_sent_at"] = 0
    fake_cache.set(service._pending_key("someone@gmail.com"), json.dumps(blob), ttl_seconds=600)

    service.resend_code("someone@gmail.com")
    assert len(fake_email.sent) == 2
    assert fake_email.sent[1][0] == "someone@gmail.com"


def test_resend_code_is_silent_about_unknown_emails(fake_cache, fake_email):
    result = service.resend_code("never-registered@gmail.com")
    assert result.email == "never-registered@gmail.com"
    assert fake_email.sent == []  # nothing to resend, but no error either


def test_verify_email_wrong_code_does_not_extend_the_window(fake_cache, fake_email):
    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    original_created_at = service._load_pending("someone@gmail.com")["created_at"]

    with pytest.raises(ValidationError):
        service.verify_email("someone@gmail.com", "000000")

    pending = service._load_pending("someone@gmail.com")
    assert pending["attempts"] == 1
    assert pending["created_at"] == original_created_at  # window didn't reset


def test_verify_email_caps_attempts(fake_cache, fake_email, monkeypatch):
    monkeypatch.setattr(service.settings, "email_verification_max_attempts", 2)
    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")

    with pytest.raises(ValidationError):
        service.verify_email("someone@gmail.com", "000000")
    with pytest.raises(ValidationError):
        service.verify_email("someone@gmail.com", "111111")
    with pytest.raises(RateLimitError):
        service.verify_email("someone@gmail.com", "222222")

    assert service._load_pending("someone@gmail.com") is None  # cleaned up after the cap


def test_verify_email_success_creates_the_user_and_logs_in(fake_cache, fake_email, monkeypatch):
    created = {}

    def _fake_create(email, password_hash, full_name, role):
        created.update(email=email, password_hash=password_hash, full_name=full_name, role=role)
        return {
            "user_id": "11111111-1111-1111-1111-111111111111", "email": email,
            "full_name": full_name, "role": role, "account_status": "active",
        }

    monkeypatch.setattr(service.repository, "create", _fake_create)

    service.start_registration("someone@gmail.com", "password123", "Test Applicant", "applicant")
    code = _extract_code(fake_email)

    response = service.verify_email("someone@gmail.com", code)
    assert response.user.email == "someone@gmail.com"
    assert response.user.role == "applicant"
    assert response.access_token
    assert created["role"] == "applicant"
    # One-time use: the pending entry is gone, a second verify fails.
    with pytest.raises(ValidationError):
        service.verify_email("someone@gmail.com", code)


def test_verify_email_with_no_pending_registration(fake_cache, fake_email):
    with pytest.raises(ValidationError):
        service.verify_email("never-registered@gmail.com", "123456")


# ---- login: role must match the account's actual stored role ------------

def _user_row(role: str = "applicant") -> dict:
    return {
        "user_id": "11111111-1111-1111-1111-111111111111", "email": "someone@gmail.com",
        "full_name": "Test User", "role": role, "account_status": "active",
        "password_hash": service.hash_password("password123"),
    }


def test_login_succeeds_when_selected_role_matches(monkeypatch):
    monkeypatch.setattr(service.repository, "get_by_email", lambda email: _user_row("applicant"))
    monkeypatch.setattr(service.repository, "update_last_login", lambda user_id: None)

    response = service.login("someone@gmail.com", "password123", "applicant")
    assert response.user.role == "applicant"


def test_login_rejects_a_mismatched_role_even_with_the_correct_password(monkeypatch):
    monkeypatch.setattr(service.repository, "get_by_email", lambda email: _user_row("applicant"))
    monkeypatch.setattr(service.repository, "update_last_login", lambda user_id: None)

    with pytest.raises(UnauthorizedError):
        service.login("someone@gmail.com", "password123", "admin")


def test_login_wrong_password_is_checked_before_role(monkeypatch):
    monkeypatch.setattr(service.repository, "get_by_email", lambda email: _user_row("applicant"))
    with pytest.raises(UnauthorizedError):
        service.login("someone@gmail.com", "wrong-password", "admin")
