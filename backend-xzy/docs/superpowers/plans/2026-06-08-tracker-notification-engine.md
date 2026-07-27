# Tracker Notification Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn #5 Tracker into a real proactive-notification engine: configurable preferences (channels/frequency/per-milestone mute), daily-digest grouping, a deduplicated "what to send now" delivery model, and real email sending via SMTP (with graceful offline degrade).

**Architecture:** The deterministic engine decides WHAT to send (`due_now`); a pluggable `Notifier` (the swap-seam, like `Retriever`/`Fetcher`) does the actual sending. Sent-state and preferences are carried on `UserProfile`. SMTP credentials come from `common/config.py` (env > `data/.smtp.json` > none); when unconfigured, delivery degrades to record-only and the suite stays fully offline.

**Tech Stack:** Python 3.11+, pydantic v2, stdlib `smtplib`/`email.message`, pytest (monkeypatch for SMTP — never real network).

**Spec:** [docs/superpowers/specs/2026-06-08-tracker-notification-engine-design.md](../specs/2026-06-08-tracker-notification-engine-design.md)

---

## Notes for the implementer

- **Not a git repo originally; now it is** (initialized this session). Commit after each task with the suggested message, or treat the "Commit" step as a checkpoint (run the suite) if you prefer.
- **Run from project root** `E:\claude program\capstone_v2`: `python -m pytest tests/ -q`.
- **Offline invariant (non-negotiable):** no test may open a real network connection. SMTP is exercised only via `monkeypatch` of `smtplib.SMTP`. `tests/conftest.py` is extended (Task 2) to isolate SMTP creds the same way it isolates DeepSeek.
- **State lives on the profile** (decided in brainstorming): `dispatch_due` mutates `profile.notification_log`. `get_profile()` in `mock_data` returns a copy, so tests get fresh state.
- **Existing behavior to preserve:** `build_reminders(profile, today, already_sent=...)` keeps its `already_sent` param (a v2 test uses it). New dedup for delivery lives in `due_now` via `notification_log`; the two don't conflict.
- **File responsibilities:**
  - `common/profile.py` — data model (prefs + sent-log + email).
  - `common/config.py` — SMTP credential lookup (no secrets in code).
  - `common/notifier.py` (new) — the send seam: protocol + recording + SMTP impls + factory.
  - `agents/tracker/reminders.py` — decide what to send (`build_reminders` mute, `due_now`) + perform send+record (`dispatch_due`).
  - `agents/tracker/agent.py` — `handle` (read-only preview) + `configure` (mutate prefs).
  - `supervisor.py` — route `configure_reminders` to the new handler.

---

## Task 1: Profile schema — prefs, email, sent-log

**Files:**
- Modify: `common/profile.py`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_tracker.py`:

```python
# ---------- notification engine: schema ----------
from common.profile import NotificationPrefs, NotificationRecord, UserProfile, LifecycleStage


def test_prefs_muted_milestones_defaults_empty():
    assert NotificationPrefs().muted_milestones == []


def test_notification_record_defaults_delivered_true():
    r = NotificationRecord(key="offer_acceptance:2026-07-15", date="2026-06-08", channels=["email"])
    assert r.delivered is True and r.channels == ["email"]


def test_profile_email_and_log_defaults():
    p = UserProfile(user_id="u", lifecycle_stage=LifecycleStage.applicant)
    assert p.email is None and p.notification_log == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tracker.py -k "muted_milestones or notification_record or email_and_log" -q`
Expected: FAIL — `cannot import name 'NotificationRecord'` / unexpected kwarg `muted_milestones`.

- [ ] **Step 3: Implement in `common/profile.py`**

Add `muted_milestones` to `NotificationPrefs`:
```python
class NotificationPrefs(BaseModel):
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.in_app]
    )
    frequency: NotificationFrequency = NotificationFrequency.immediate
    muted_milestones: list[str] = Field(default_factory=list)  # milestone keys to suppress
```

Add a new model just after `NotificationPrefs`:
```python
class NotificationRecord(BaseModel):
    """One dispatched-notification record, carried on the profile for dedup + audit."""

    key: str            # reminder key, e.g. "offer_acceptance:2026-07-15"
    date: str           # ISO date dispatched
    channels: list[str] = Field(default_factory=list)
    delivered: bool = True   # False if a real send failed (record kept for dedup)
```

Add two fields to `UserProfile` (place `email` near the identity block, `notification_log` near `notification_prefs`):
```python
    email: str | None = None  # recipient address for the email channel
```
```python
    notification_log: list[NotificationRecord] = Field(default_factory=list)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tracker.py -k "muted_milestones or notification_record or email_and_log" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add common/profile.py tests/test_tracker.py
git commit -m "feat(#5): profile fields for notification prefs, email, sent-log"
```

---

## Task 2: SMTP config + test isolation

**Files:**
- Modify: `common/config.py`, `.gitignore`, `tests/conftest.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_config.py`:

```python
# ---------- SMTP config ----------
def test_smtp_not_configured_when_empty(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert config.smtp_configured() is False


def test_smtp_configured_from_env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert config.smtp_configured() is True
    assert config.get_smtp_host() == "smtp.example.com"
    assert config.get_smtp_port() == 587          # default
    assert config.get_smtp_from() == "me@example.com"  # defaults to username
    assert config.get_smtp_use_tls() is True      # default
```

(`config` is already imported at the top of `tests/test_config.py`. If not, add `from common import config`.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_config.py -k smtp -q`
Expected: FAIL — `module 'common.config' has no attribute 'smtp_configured'`.

- [ ] **Step 3: Implement in `common/config.py`**

Add near the other module constants:
```python
_SMTP_FILE = Path(__file__).resolve().parents[1] / "data" / ".smtp.json"
_DEFAULT_SMTP_PORT = 587


def _read_smtp_file() -> dict:
    if not _SMTP_FILE.exists():
        return {}
    try:
        return json.loads(_SMTP_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
```

Add the accessors (env > file > default):
```python
def get_smtp_host() -> str | None:
    return os.getenv("SMTP_HOST") or _read_smtp_file().get("smtp_host") or None


def get_smtp_port() -> int:
    val = os.getenv("SMTP_PORT") or _read_smtp_file().get("smtp_port") or _DEFAULT_SMTP_PORT
    try:
        return int(val)
    except (TypeError, ValueError):
        return _DEFAULT_SMTP_PORT


def get_smtp_username() -> str | None:
    return os.getenv("SMTP_USERNAME") or _read_smtp_file().get("smtp_username") or None


def get_smtp_password() -> str | None:
    return os.getenv("SMTP_PASSWORD") or _read_smtp_file().get("smtp_password") or None


def get_smtp_from() -> str | None:
    return (
        os.getenv("SMTP_FROM")
        or _read_smtp_file().get("smtp_from")
        or get_smtp_username()
    )


def get_smtp_use_tls() -> bool:
    env = os.getenv("SMTP_USE_TLS")
    if env is not None:
        return env.strip().lower() not in ("0", "false", "no")
    file_val = _read_smtp_file().get("smtp_use_tls")
    return True if file_val is None else bool(file_val)


def smtp_configured() -> bool:
    return bool(get_smtp_host() and get_smtp_username() and get_smtp_password())
```

- [ ] **Step 4: Extend test isolation** — in `tests/conftest.py`, inside `_isolate_credentials`, add (before `yield`):
```python
    for _k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
               "SMTP_FROM", "SMTP_USE_TLS"):
        monkeypatch.delenv(_k, raising=False)
    monkeypatch.setattr(config, "_SMTP_FILE", tmp_path / "isolated.smtp.json")
```

- [ ] **Step 5: Add to `.gitignore`** — under the DeepSeek credentials line, add:
```
# Local SMTP credentials (never commit)
data/.smtp.json
```

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_config.py -k smtp -q`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add common/config.py tests/test_config.py tests/conftest.py .gitignore
git commit -m "feat(#5): SMTP credential config + test isolation"
```

---

## Task 3: Notifier seam (recording + SMTP)

**Files:**
- Create: `common/notifier.py`
- Test: `tests/test_notifier.py` (new)

- [ ] **Step 1: Write the failing tests** — create `tests/test_notifier.py`:

```python
"""Tests for the pluggable Notifier seam. No real network — SMTP is monkeypatched."""
from common import config
from common.notifier import RecordingNotifier, SmtpEmailNotifier, get_notifier


def test_recording_notifier_send_is_noop_true():
    assert RecordingNotifier().send("a@b.com", "subj", "body") is True


def test_get_notifier_returns_recording_when_unconfigured():
    # conftest clears SMTP creds, so this is the offline default.
    assert isinstance(get_notifier(), RecordingNotifier)


def test_get_notifier_returns_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert isinstance(get_notifier(), SmtpEmailNotifier)


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent_messages = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, pwd):
        self.logged_in = (user, pwd)

    def send_message(self, msg):
        self.sent_messages.append(msg)


def test_smtp_notifier_builds_and_sends_message(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    _FakeSMTP.instances.clear()
    monkeypatch.setattr("common.notifier.smtplib.SMTP", _FakeSMTP)

    ok = SmtpEmailNotifier().send("applicant@x.com", "Hello", "Body text")
    assert ok is True
    srv = _FakeSMTP.instances[-1]
    assert srv.started_tls is True
    assert srv.logged_in == ("me@example.com", "secret")
    msg = srv.sent_messages[-1]
    assert msg["To"] == "applicant@x.com"
    assert msg["From"] == "noreply@example.com"
    assert msg["Subject"] == "Hello"
    assert "Body text" in msg.get_content()


def test_smtp_notifier_returns_false_on_error(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr("common.notifier.smtplib.SMTP", _boom)
    assert SmtpEmailNotifier().send("a@b.com", "s", "b") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_notifier.py -q`
Expected: FAIL — `No module named 'common.notifier'`.

- [ ] **Step 3: Implement `common/notifier.py`**

```python
"""Pluggable notification delivery seam.

The deterministic engine decides WHAT to send; a Notifier delivers it. This is
the "swap delivery on deployment" seam (cf. Retriever / Fetcher). Default is the
offline RecordingNotifier; configure SMTP credentials (common/config.py) to get
real email via SmtpEmailNotifier. Sending never raises — failures return False.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from common import config


class Notifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...


class RecordingNotifier:
    """Offline default: performs no external delivery (caller records the log)."""

    def send(self, to: str, subject: str, body: str) -> bool:
        return True


class SmtpEmailNotifier:
    """Sends plain-text email via stdlib smtplib. Returns False on any failure."""

    def send(self, to: str, subject: str, body: str) -> bool:
        host = config.get_smtp_host()
        if not host or not to:
            return False
        msg = EmailMessage()
        msg["From"] = config.get_smtp_from() or config.get_smtp_username() or ""
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(host, config.get_smtp_port(), timeout=10) as server:
                if config.get_smtp_use_tls():
                    server.starttls()
                username = config.get_smtp_username()
                password = config.get_smtp_password()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
            return True
        except Exception:
            return False


def get_notifier() -> Notifier:
    """SMTP notifier when credentials are configured, else the offline recorder."""
    return SmtpEmailNotifier() if config.smtp_configured() else RecordingNotifier()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_notifier.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add common/notifier.py tests/test_notifier.py
git commit -m "feat(#5): pluggable Notifier seam with SMTP email + offline default"
```

---

## Task 4: Reminders engine — mute gating, Notification, due_now

**Files:**
- Modify: `agents/tracker/reminders.py`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_tracker.py`:

```python
# ---------- notification engine: mute + due_now ----------
from datetime import date as _date

from agents.tracker.reminders import Notification, build_reminders as _build, due_now
from common.profile import NotificationFrequency as _Freq


def _two_due_profile():
    """DOCS_REQUIRED profile with TWO milestones firing at once (digest demo)."""
    p = mock_data.get_profile("4")
    p.application.status_code = StatusCode.DOCS_REQUIRED
    p.application.deadlines = {
        "application_deadline": "2026-06-10",
        "document_deadline": "2026-06-10",
    }
    p.notification_log = []
    return p


def test_muted_milestone_is_suppressed():
    p = mock_data.get_profile("3")  # document_deadline 2026-06-10, DOCS_REQUIRED
    p.notification_prefs.muted_milestones = ["document_deadline"]
    assert _build(p, today=_date(2026, 5, 30)) == []


def test_due_now_immediate_one_per_reminder():
    p = _two_due_profile()
    p.notification_prefs.frequency = _Freq.immediate
    notes = due_now(p, today=_date(2026, 6, 5))
    assert len(notes) == 2
    assert all(n.kind == "single" for n in notes)
    assert all(len(n.reminder_keys) == 1 for n in notes)


def test_due_now_digest_groups_into_one():
    p = _two_due_profile()
    p.notification_prefs.frequency = _Freq.daily_digest
    notes = due_now(p, today=_date(2026, 6, 5))
    assert len(notes) == 1
    assert notes[0].kind == "digest"
    assert set(notes[0].reminder_keys) == {
        "application_deadline:2026-06-10", "document_deadline:2026-06-10"}


def test_due_now_skips_already_logged():
    from common.profile import NotificationRecord
    p = _two_due_profile()
    p.notification_log = [NotificationRecord(
        key="application_deadline:2026-06-10", date="2026-06-04", channels=["in_app"])]
    notes = due_now(p, today=_date(2026, 6, 5))
    keys = {k for n in notes for k in n.reminder_keys}
    assert "application_deadline:2026-06-10" not in keys
    assert "document_deadline:2026-06-10" in keys


def test_due_now_off_is_empty():
    p = _two_due_profile()
    p.notification_prefs.frequency = _Freq.off
    assert due_now(p, today=_date(2026, 6, 5)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tracker.py -k "muted_milestone or due_now" -q`
Expected: FAIL — `cannot import name 'Notification'` / `due_now`.

- [ ] **Step 3: Implement in `agents/tracker/reminders.py`**

In `build_reminders`, add mute gating. Find the loop `for name, iso in profile.application.deadlines.items():` and immediately after the `ms = _MILESTONES.get(...)` line add:
```python
        if name in profile.notification_prefs.muted_milestones:
            continue  # user muted this milestone type
```

Add at the end of the file (`dataclass` and `field` are already imported at the top of `reminders.py` — reuse them, do not re-import):
```python
@dataclass
class Notification:
    kind: str                 # "single" | "digest"
    channels: list[str]
    date: str                 # ISO (today)
    subject: str
    message: str
    urgency: str              # info | soon | urgent (digest takes the most urgent)
    reminder_keys: list[str]


_URGENCY_RANK = {"info": 0, "soon": 1, "urgent": 2}
_SUBJECT_PREFIX = "NUS MSc DFinTech 提醒"


def due_now(profile: UserProfile, today: date | None = None) -> list[Notification]:
    """What should be delivered now: relevant reminders minus already-logged ones,
    shaped by frequency. Pure read — does NOT mutate the profile."""
    today = today or date.today()
    candidates = build_reminders(profile, today=today)  # consent/off/mute/window/status gated
    if not candidates:
        return []
    sent = {rec.key for rec in profile.notification_log}
    pending = [r for r in candidates if r.key not in sent]
    if not pending:
        return []
    channels = [c.value for c in profile.notification_prefs.channels]
    iso_today = today.isoformat()
    if profile.notification_prefs.frequency == NotificationFrequency.daily_digest:
        urgency = max((r.urgency for r in pending), key=lambda u: _URGENCY_RANK.get(u, 0))
        body = "你有以下待办提醒:\n" + "\n".join(f"· {r.message}" for r in pending)
        return [Notification(
            kind="digest", channels=channels, date=iso_today,
            subject=f"{_SUBJECT_PREFIX}:你有 {len(pending)} 条待办",
            message=body, urgency=urgency,
            reminder_keys=[r.key for r in pending],
        )]
    return [
        Notification(
            kind="single", channels=channels, date=iso_today,
            subject=f"{_SUBJECT_PREFIX}:{_MILESTONES.get(r.name, {}).get('label', r.name)}",
            message=r.message, urgency=r.urgency, reminder_keys=[r.key],
        )
        for r in pending
    ]
```

Add `UserProfile` to the existing profile import at the top of the file (it currently imports `NotificationFrequency, StatusCode, UserProfile` — verify `UserProfile` is present; if not, add it).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tracker.py -k "muted_milestone or due_now" -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/tracker/reminders.py tests/test_tracker.py
git commit -m "feat(#5): mute gating + Notification/due_now (digest grouping + dedup)"
```

---

## Task 5: dispatch_due — send + record (with digest sub-keys)

**Files:**
- Modify: `agents/tracker/reminders.py`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_tracker.py`:

```python
# ---------- notification engine: dispatch ----------
from agents.tracker.reminders import dispatch_due
from common.notifier import RecordingNotifier


def test_dispatch_records_log_and_dedupes():
    p = _two_due_profile()
    notes = dispatch_due(p, today=_date(2026, 6, 5), notifier=RecordingNotifier())
    assert notes  # something was dispatched
    assert {r.key for r in p.notification_log} == {
        "application_deadline:2026-06-10", "document_deadline:2026-06-10"}
    # second dispatch finds nothing new (dedup via log)
    assert dispatch_due(p, today=_date(2026, 6, 6), notifier=RecordingNotifier()) == []


def test_digest_then_immediate_does_not_resend():
    p = _two_due_profile()
    p.notification_prefs.frequency = _Freq.daily_digest
    dispatch_due(p, today=_date(2026, 6, 5), notifier=RecordingNotifier())
    # switch to immediate next day -> nothing re-fires (sub-keys were recorded)
    p.notification_prefs.frequency = _Freq.immediate
    assert due_now(p, today=_date(2026, 6, 6)) == []


def test_dispatch_email_skipped_when_no_address():
    sent = []

    class _SpyNotifier:
        def send(self, to, subject, body):
            sent.append(to)
            return True

    p = _two_due_profile()
    p.email = None
    p.notification_prefs.channels = [NotificationChannel.email]
    dispatch_due(p, today=_date(2026, 6, 5), notifier=_SpyNotifier())
    assert sent == []                       # no email attempted without an address
    assert p.notification_log                # but still recorded (in_app-style)


def test_dispatch_sends_email_when_address_present():
    sent = []

    class _SpyNotifier:
        def send(self, to, subject, body):
            sent.append((to, subject))
            return True

    p = _two_due_profile()
    p.email = "applicant@x.com"
    p.notification_prefs.channels = [NotificationChannel.email]
    dispatch_due(p, today=_date(2026, 6, 5), notifier=_SpyNotifier())
    assert sent and all(to == "applicant@x.com" for to, _ in sent)


def test_dispatch_failed_send_marks_not_delivered():
    class _FailNotifier:
        def send(self, to, subject, body):
            return False

    p = _two_due_profile()
    p.email = "applicant@x.com"
    p.notification_prefs.channels = [NotificationChannel.email]
    dispatch_due(p, today=_date(2026, 6, 5), notifier=_FailNotifier())
    assert p.notification_log and all(r.delivered is False for r in p.notification_log)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tracker.py -k dispatch -q`
Expected: FAIL — `cannot import name 'dispatch_due'`.

- [ ] **Step 3: Implement in `agents/tracker/reminders.py`**

Add imports at the top (with the others):
```python
from common.notifier import Notifier, get_notifier
from common.profile import NotificationRecord
```
Add at the end of the file:
```python
def dispatch_due(profile: UserProfile, today: date | None = None,
                 notifier: Notifier | None = None) -> list[Notification]:
    """Deliver due notifications and record them on the profile (mutates the log).

    Email channel sends via the notifier only when the profile has an email
    address; in-app is record-only. A failed real send is still recorded (with
    delivered=False) so it is not retried and remains auditable."""
    today = today or date.today()
    notifier = notifier or get_notifier()
    notes = due_now(profile, today=today)
    for n in notes:
        delivered = True
        if "email" in n.channels and profile.email:
            ok = notifier.send(profile.email, n.subject, n.message)
            delivered = delivered and ok
        for key in n.reminder_keys:  # digest records each sub-key -> only-once across frequencies
            profile.notification_log.append(NotificationRecord(
                key=key, date=n.date, channels=list(n.channels), delivered=delivered,
            ))
    return notes
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tracker.py -k dispatch -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/tracker/reminders.py tests/test_tracker.py
git commit -m "feat(#5): dispatch_due sends via notifier and records the sent-log"
```

---

## Task 6: Agent — configure_reminders + due_now preview

**Files:**
- Modify: `agents/tracker/agent.py`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_tracker.py`:

```python
# ---------- notification engine: configure + preview ----------
from agents.tracker.agent import configure


def test_configure_updates_prefs():
    p = mock_data.get_profile("4")
    resp = configure(p, {"frequency": "daily_digest", "channels": ["email"],
                         "mute": ["application_deadline"]})
    assert resp.status == "ok"
    assert p.notification_prefs.frequency == NotificationFrequency.daily_digest
    assert [c.value for c in p.notification_prefs.channels] == ["email"]
    assert "application_deadline" in p.notification_prefs.muted_milestones
    assert resp.data["notification_prefs"]["frequency"] == "daily_digest"


def test_configure_unmute_removes_milestone():
    p = mock_data.get_profile("4")
    p.notification_prefs.muted_milestones = ["application_deadline"]
    configure(p, {"unmute": ["application_deadline"]})
    assert p.notification_prefs.muted_milestones == []


def test_configure_rejects_invalid_value():
    p = mock_data.get_profile("4")
    resp = configure(p, {"frequency": "hourly"})  # not a valid frequency
    assert resp.status == "need_clarification"
    assert "frequency" in resp.missing_fields


def test_configure_rejects_unknown_milestone():
    p = mock_data.get_profile("4")
    resp = configure(p, {"mute": ["not_a_milestone"]})
    assert resp.status == "need_clarification"


def test_handle_includes_due_now_preview_without_logging():
    p = _two_due_profile()
    resp = handle(p, {"today": "2026-06-05"})
    assert resp.data["due_now"]              # preview present
    assert p.notification_log == []          # preview did NOT write the log
    assert "muted_milestones" in resp.data["notification_prefs"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tracker.py -k "configure or due_now_preview" -q`
Expected: FAIL — `cannot import name 'configure'`.

- [ ] **Step 3: Implement in `agents/tracker/agent.py`**

Add imports at the top (with the existing ones):
```python
from common.profile import NotificationChannel, NotificationFrequency
from .reminders import build_reminders, due_now, _MILESTONES
```
(`build_reminders` is already imported — keep a single import line; add `due_now` and `_MILESTONES`.)

Add the `configure` handler (after `handle`):
```python
def _prefs_dict(profile: UserProfile) -> dict:
    p = profile.notification_prefs
    return {
        "channels": [c.value for c in p.channels],
        "frequency": p.frequency.value,
        "muted_milestones": list(p.muted_milestones),
    }


def configure(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    """Update notification preferences (channels / frequency / per-milestone mute).

    Validates against the controlled vocabularies; invalid input returns
    need_clarification rather than silently dropping the change."""
    slots = slots or {}
    invalid: list[str] = []

    new_channels = profile.notification_prefs.channels
    if "channels" in slots:
        try:
            new_channels = [NotificationChannel(c) for c in slots["channels"]]
        except ValueError:
            invalid.append("channels")

    new_freq = profile.notification_prefs.frequency
    if "frequency" in slots:
        try:
            new_freq = NotificationFrequency(slots["frequency"])
        except ValueError:
            invalid.append("frequency")

    known = set(_MILESTONES.keys())
    mute = list(slots.get("mute", []))
    unmute = list(slots.get("unmute", []))
    if any(m not in known for m in (*mute, *unmute)):
        invalid.append("milestone")

    if invalid:
        return AgentResponse.needs(
            invalid,
            "有无法识别的通知设置项,请检查后重试:" + "、".join(invalid),
        )

    muted = [m for m in profile.notification_prefs.muted_milestones if m not in unmute]
    for m in mute:
        if m not in muted:
            muted.append(m)

    profile.notification_prefs.channels = new_channels
    profile.notification_prefs.frequency = new_freq
    profile.notification_prefs.muted_milestones = muted

    prefs = _prefs_dict(profile)
    speakable = (
        f"已更新通知设置:渠道 {', '.join(prefs['channels'])};"
        f"频率 {prefs['frequency']}"
        + (f";已静音 {', '.join(prefs['muted_milestones'])}" if prefs["muted_milestones"] else "")
        + "。"
    )
    return AgentResponse(
        status="ok",
        answer_type="advisory",
        speakable=speakable,
        data={"notification_prefs": prefs},
    )
```

In `handle`, add a read-only `due_now` preview. Find the `reminders = build_reminders(profile, today=today)` line and after it add:
```python
    due = due_now(profile, today=today)  # preview only; does NOT write the log
    due_data = [
        {"kind": n.kind, "channels": n.channels, "date": n.date, "subject": n.subject,
         "message": n.message, "urgency": n.urgency, "reminder_keys": n.reminder_keys}
        for n in due
    ]
```
Then in the returned `data={...}` dict, add `"due_now": due_data,` and replace the existing `notification_prefs` block with `"notification_prefs": _prefs_dict(profile),` (so it includes `muted_milestones`).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tracker.py -k "configure or due_now_preview" -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/tracker/agent.py tests/test_tracker.py
git commit -m "feat(#5): configure_reminders handler + read-only due_now preview"
```

---

## Task 7: Supervisor routing for configure_reminders

**Files:**
- Modify: `supervisor.py:20`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_tracker.py`:

```python
# ---------- notification engine: routing ----------
def test_supervisor_routes_configure_to_configure_handler():
    from supervisor import route
    p = mock_data.get_profile("4")
    resp = route("configure_reminders", p, {"frequency": "off"})
    assert resp.status == "ok"
    assert p.notification_prefs.frequency == NotificationFrequency.off
    assert resp.data["notification_prefs"]["frequency"] == "off"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tracker.py -k routes_configure -q`
Expected: FAIL — current route points at `handle`, which returns status (no prefs change); `data["notification_prefs"]["frequency"]` stays `immediate`, assertion fails.

- [ ] **Step 3: Implement in `supervisor.py`**

Change the `_ROUTES` entry for `configure_reminders` (line 20) from:
```python
    "configure_reminders": ("agents.tracker.agent", "handle"),
```
to:
```python
    "configure_reminders": ("agents.tracker.agent", "configure"),
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tracker.py -k routes_configure -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add supervisor.py tests/test_tracker.py
git commit -m "feat(#5): route configure_reminders to the configure handler"
```

---

## Task 8: Demo data + CLI notify demo

**Files:**
- Modify: `common/mock_data.py`, `run.py`
- Test: none new (covered by Task 5/6); verify the demo runs

- [ ] **Step 1: Add an email to the demo applicants** — in `common/mock_data.py`, inside profile `"4"` and profile `"5"`, add an `email` field on the `UserProfile(...)` (e.g. right after `authenticated=True` or `user_id`):
```python
        email="demo.applicant@example.com",
```
(Both profiles already set `notification_prefs` with in_app+email channels, so this makes the email channel exercisable in the demo.)

- [ ] **Step 2: Add a `notify` CLI demo** — in `run.py`, locate the subcommand dispatch (where `checklist`/`status`/`compare`/`courses` are handled) and add a `notify` branch that demonstrates due → dispatch → dedup. Use the existing arg/profile-loading pattern in the file; the body:
```python
        elif args.command == "notify":
            from datetime import date
            from agents.tracker.reminders import due_now, dispatch_due
            profile = mock_data.get_profile(args.profile)
            today = date(2026, 6, 5)
            print("== due now (preview) ==")
            for n in due_now(profile, today=today):
                print(f"[{n.urgency}] {n.subject} -> {n.channels}: {n.message}")
            print("== dispatch (record-only unless SMTP configured) ==")
            sent = dispatch_due(profile, today=today)
            print(f"dispatched {len(sent)} notification(s); log now has {len(profile.notification_log)} record(s)")
            print("== due now again (should be empty after dispatch) ==")
            print(due_now(profile, today=today) or "（无,已全部发送并去重）")
```
Match `run.py`'s actual argument parsing (it already supports `--profile`); register `notify` alongside the other commands in the same place they are declared (e.g. an argparse `choices=[...]` list or an `if/elif` chain — follow whatever the file already does).

- [ ] **Step 3: Verify the demo runs**

Run: `python run.py notify --profile 5`
Expected: prints a due-now list, a dispatch line, then "（无,已全部发送并去重）". No traceback. (Records only; no real email unless SMTP configured.)

- [ ] **Step 4: Verify no regressions**

Run: `python -m pytest tests/ -q`
Expected: full suite PASS.

- [ ] **Step 5: Commit**

```bash
git add common/mock_data.py run.py
git commit -m "feat(#5): demo email on mock applicants + run.py notify demo"
```

---

## Task 9: Docs — contract, design, changelog, overview

**Files:**
- Modify: `docs/02-interface-contracts.md`, `docs/08-tracker-v2-design.md`, `CHANGELOG.md`, `docs/00-project-overview.md`

- [ ] **Step 1: Update contract `docs/02-interface-contracts.md`** — under the `#5 get_application_status → data` section, add the `due_now` + extended prefs fields, and add a new `configure_reminders` block:

````markdown
> v3 (通知引擎): `get_application_status` 的 `data` 增加 `due_now`(本次应投递的通知预览,只读不发) 与 `notification_prefs.muted_milestones`。

### #5 `configure_reminders` → data
```jsonc
// 入站 slots: {"channels":["in_app","email"], "frequency":"daily_digest",
//             "mute":["application_deadline"], "unmute":["offer_acceptance"]}
{
  "notification_prefs": {
    "channels": ["email"],
    "frequency": "daily_digest",
    "muted_milestones": ["application_deadline"]
  }
}
```
> 非法值(渠道/频率/里程碑)→ `status="need_clarification"`,`missing_fields` 标出问题项。真实发送由 `dispatch_due` 经可插拔 `Notifier` 完成(配 SMTP 才真发,否则 record-only)。
````

- [ ] **Step 2: Add a v3 note to `docs/08-tracker-v2-design.md`** — at the top, after the status line:
```markdown
> **v3 起(2026-06-08)通知引擎**:新增 `configure_reminders`(改 channels/frequency/按里程碑静音)、`daily_digest` 分组、`due_now`/`dispatch_due` 去重投递模型,并经可插拔 `Notifier`(`common/notifier.py`)**真发邮件**(SMTP via `common/config.py`,未配置则 record-only)。sent-state 携带在 `UserProfile.notification_log`。见 [v3 spec](superpowers/specs/2026-06-08-tracker-notification-engine-design.md) 与 [plan](superpowers/plans/2026-06-08-tracker-notification-engine.md)。
```

- [ ] **Step 3: Prepend a CHANGELOG entry** under `## [Unreleased]` in `CHANGELOG.md`:
```markdown
### 2026-06-08 (4)
- **#5 · Tracker 通知引擎(已落地)**:`configure_reminders` intent(改渠道/频率/按里程碑静音,非法值打回);`daily_digest` 合并分组;`due_now` 去重(profile.notification_log)+ `dispatch_due` 投递并记录(digest 记子 key→跨频率只发一次);可插拔 `Notifier`(`common/notifier.py`:RecordingNotifier 离线默认 + SmtpEmailNotifier 真发邮件,`get_notifier()` 按 `config.smtp_configured()` 选);SMTP 凭据走 `common/config.py`(env > data/.smtp.json,已 gitignore);profile 加 `email`/`muted_milestones`/`notification_log`;supervisor 路由 configure_reminders→configure;handle 加只读 due_now 预览。测试离线(monkeypatch smtplib)。
```

- [ ] **Step 4: Update `docs/00-project-overview.md`** — in the §4 agent table, change the #5 Tracker "关键特性" cell to mention the notification engine + real email:
```markdown
| 5 | Tracker | 状态机 + 状态翻译 + 截止提醒 | 状态码翻人话 + 下一步 | mock 状态机;**通知引擎:configure_reminders + daily_digest + due_now/dispatch 去重 + 可插拔 Notifier 真发邮件(SMTP,未配则离线 record-only)** |
```

- [ ] **Step 5: Commit**

```bash
git add docs/ CHANGELOG.md
git commit -m "docs(#5): document tracker notification engine + email"
```

---

## Task 10: Final verification

- [ ] **Step 1: Full suite** — Run: `python -m pytest tests/ -q` — Expected: all PASS (baseline 220 passed +1 skipped; this adds ~24 tests).
- [ ] **Step 2: Eval regression** — Run: `python -m eval.runner` — Expected: `12/12` (unchanged; tracker not in eval cases).
- [ ] **Step 3: CLI smokes** — Run: `python run.py status --profile 4` and `python run.py notify --profile 5` — Expected: no traceback; `notify` shows due → dispatch → empty.
- [ ] **Step 4: Offline confirsmation** — Confirm no test required network: the suite passed in Step 1 with SMTP creds isolated by conftest, so `get_notifier()` returned `RecordingNotifier` and `SmtpEmailNotifier` was only exercised via monkeypatched `smtplib.SMTP`.
```
