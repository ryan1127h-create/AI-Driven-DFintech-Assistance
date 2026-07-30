"""Deterministic tests for #5 tracker (status translation + reminders)."""
from datetime import date

from app.agents.tracker.agent import handle
from app.agents.tracker.reminders import build_reminders
from app.agents.tracker.statemachine import (
    build_timeline,
    estimated_next_date,
    latest_status_date,
    next_states,
    translate,
)
from common import mock_data
from common.profile import NotificationChannel, NotificationFrequency, StatusCode


def test_translate_known_status():
    t = translate(StatusCode.UNDER_REVIEW)
    assert t["human_status"] and t["next_step"]


def test_next_states_terminal():
    assert next_states(StatusCode.REJECTED) == []
    assert "ACCEPTED" in next_states(StatusCode.OFFER)


def test_reminder_within_window_for_docs_required():
    p = mock_data.get_profile("3")  # document_deadline 2026-06-10, DOCS_REQUIRED
    rs = build_reminders(p, today=date(2026, 5, 30))
    assert len(rs) == 1
    assert rs[0].name == "document_deadline"
    assert "materials" in rs[0].message


def test_reminder_outside_window_suppressed():
    p = mock_data.get_profile("1")  # offer_acceptance 2026-07-15, 46 days out
    rs = build_reminders(p, today=date(2026, 5, 30))
    assert rs == []


def test_reminder_requires_consent():
    p = mock_data.get_profile("3")
    p.consent_flags.reminders = False
    assert build_reminders(p, today=date(2026, 5, 30)) == []


def test_frequency_control_dedup():
    p = mock_data.get_profile("3")
    key = "document_deadline:2026-06-10"
    assert build_reminders(p, today=date(2026, 5, 30), already_sent={key}) == []


def test_urgency_escalates_near_deadline():
    p = mock_data.get_profile("3")
    rs = build_reminders(p, today=date(2026, 6, 8))  # 2 days left
    assert rs[0].urgency == "urgent"


def test_handle_envelope():
    p = mock_data.get_profile("3")
    resp = handle(p, {"today": "2026-05-30"})
    assert resp.status == "ok"
    assert resp.data["status_code"] == "DOCS_REQUIRED"
    assert resp.data["reminders"]


# ---------- v2: timeline + estimated date ----------
def test_timeline_is_translated_and_sorted():
    p = mock_data.get_profile("4")
    tl = build_timeline(p.application)
    assert [e["status_code"] for e in tl] == ["SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED"]
    assert tl[-1]["human_status"] and tl[-1]["note"]  # translated + note carried


def test_estimated_next_date_uses_eta_days():
    # DOCS_REQUIRED reached 2026-05-25, eta_days=7 -> 2026-06-01.
    p = mock_data.get_profile("4")
    since = latest_status_date(p.application)
    assert estimated_next_date(StatusCode.DOCS_REQUIRED, since) == "2026-06-01"


def test_estimated_next_date_none_without_eta():
    assert estimated_next_date(StatusCode.WAITLIST, "2026-05-01") is None


# ---------- v2: #4 linkage ----------
def test_docs_required_lists_outstanding_documents():
    p = mock_data.get_profile("4")
    resp = handle(p, {"today": "2026-05-31"})
    keys = {d["key"] for d in resp.data["outstanding_documents"]}
    assert "transcript" in keys  # rejected -> outstanding
    # the rejected transcript is reported with its status
    transcript = next(d for d in resp.data["outstanding_documents"] if d["key"] == "transcript")
    assert transcript["status"] == "rejected"


def test_outstanding_documents_exclude_optional_material():
    """Only required items block: #5's list must match #4's outstanding_count."""
    from app.agents.checklist.engine import build_checklist

    p = mock_data.get_profile("4")
    required_outstanding = build_checklist(p).outstanding_count
    resp = handle(p, {"today": "2026-05-31"})
    blocking = resp.data["outstanding_documents"]
    assert len(blocking) == required_outstanding
    # optional supporting material is reported separately, never as blocking
    assert "other_supporting_documents" not in {d["key"] for d in blocking}
    assert "other_supporting_documents" in {d["key"] for d in resp.data["optional_documents"]}


def test_next_step_count_agrees_with_the_itemised_list():
    """The spoken count is the #4 required count and names every listed item."""
    from app.agents.checklist.engine import build_checklist

    p = mock_data.get_profile("4")
    required_outstanding = build_checklist(p).outstanding_count
    resp = handle(p, {"today": "2026-05-31"})
    next_step = resp.data["next_step"]
    assert f"You still have {required_outstanding} required item(s) to handle" in next_step
    for doc in resp.data["outstanding_documents"]:
        assert doc["label"] in next_step


def test_english_output_uses_no_chinese_punctuation():
    p = mock_data.get_profile("4")
    resp = handle(p, {"today": "2026-05-31"})
    for text in (resp.speakable, resp.data["next_step"]):
        assert not set(text) & set("、。，（）；：")


# ---------- v2: notification preferences ----------
def test_frequency_off_suppresses_reminders():
    p = mock_data.get_profile("4")
    p.notification_prefs.frequency = NotificationFrequency.off
    assert build_reminders(p, today=date(2026, 5, 31)) == []


def test_reminders_carry_channels():
    p = mock_data.get_profile("4")
    rs = build_reminders(p, today=date(2026, 5, 31))
    assert rs and rs[0].channels == ["in_app", "email"]


# ---------- v2: milestone status gating ----------
def test_offer_acceptance_only_reminds_when_offer():
    p = mock_data.get_profile("1")  # UNDER_REVIEW, has offer_acceptance deadline
    # within window but wrong status -> no reminder
    assert build_reminders(p, today=date(2026, 7, 5)) == []
    # flip to OFFER -> reminder fires
    p.application.status_code = StatusCode.OFFER
    rs = build_reminders(p, today=date(2026, 7, 5))
    assert rs and rs[0].name == "offer_acceptance"


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


# ---------- notification engine: mute + due_now ----------
from datetime import date as _date

from app.agents.tracker.reminders import Notification, build_reminders as _build, due_now
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


# ---------- notification engine: dispatch ----------
from app.agents.tracker.reminders import dispatch_due
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
    assert p.notification_log                # but still recorded


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


# ---------- notification engine: configure + preview ----------
from app.agents.tracker.agent import configure


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


# ---------- notification engine: routing ----------
def test_supervisor_routes_configure_to_configure_handler():
    from supervisor import route
    p = mock_data.get_profile("4")
    resp = route("configure_reminders", p, {"frequency": "off"})
    assert resp.status == "ok"
    assert p.notification_prefs.frequency == NotificationFrequency.off
    assert resp.data["notification_prefs"]["frequency"] == "off"
