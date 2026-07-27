"""Tests for the pluggable Notifier seam. No real network — SMTP is monkeypatched."""
from common import config
from common.notifier import RecordingNotifier, SmtpEmailNotifier, get_notifier


def test_recording_notifier_send_is_noop_true():
    assert RecordingNotifier().send("a@b.com", "subj", "body") is True


def test_get_notifier_returns_recording_when_unconfigured():
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


def test_smtp_notifier_uses_ssl_on_port_465(monkeypatch):
    # 163/QQ-style implicit-SSL: port 465 must use SMTP_SSL and NOT call starttls.
    monkeypatch.setenv("SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@163.com")
    monkeypatch.setenv("SMTP_PASSWORD", "authcode")
    monkeypatch.setenv("SMTP_PORT", "465")
    ssl_instances = []

    class _FakeSMTPSSL(_FakeSMTP):
        def __init__(self, host, port, timeout=None):
            super().__init__(host, port, timeout)
            ssl_instances.append(self)

    monkeypatch.setattr("common.notifier.smtplib.SMTP_SSL", _FakeSMTPSSL)

    def _no_plain(*a, **k):
        raise AssertionError("must use SMTP_SSL (not plain SMTP) on port 465")

    monkeypatch.setattr("common.notifier.smtplib.SMTP", _no_plain)

    ok = SmtpEmailNotifier().send("applicant@x.com", "Hi", "Body")
    assert ok is True
    srv = ssl_instances[-1]
    assert srv.started_tls is False          # implicit SSL: no STARTTLS
    assert srv.logged_in == ("me@163.com", "authcode")
    assert srv.sent_messages[-1]["To"] == "applicant@x.com"


def test_smtp_notifier_returns_false_on_error(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr("common.notifier.smtplib.SMTP", _boom)
    assert SmtpEmailNotifier().send("a@b.com", "s", "b") is False
