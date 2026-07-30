"""Smoke tests for the student-facing web UI (no LLM key needed)."""
from datetime import date, timedelta

import pytest

from student import webapp
from student.profile_form import (
    DEFAULT_APPLICATION_DEADLINE,
    ProfileFormError,
    build_profile,
    normalize_stage,
)


class _FakeForm(dict):
    """Mimic Flask request.form: .get + .getlist."""
    def getlist(self, key):
        v = self.get(key, [])
        return v if isinstance(v, list) else [v]


@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


# ---------- profile builder ----------
def test_build_profile_full():
    form = _FakeForm({
        "lifecycle_stage": "applicant",
        "degree_level": "bachelor",
        "field_of_study": "computer_science",
        "work_years": "2",
        "country": "in",
        "technical_proficiency": "intermediate",
        "finance_knowledge": "basic",
        "target_roles": ["fintech_pm", "quant_risk"],
        "application_type": "full_time",
        "submitted_documents": ["cv"],
    })
    p = build_profile(form)
    assert p.academic_background.field_of_study.value == "computer_science"
    assert p.country == "IN"  # upper-cased
    assert [r.value for r in p.target_roles] == ["fintech_pm", "quant_risk"]
    assert p.application.submitted_documents == ["cv"]


def test_build_profile_minimal_defaults_applicant():
    p = build_profile(_FakeForm({}))
    assert p.lifecycle_stage.value == "applicant"
    assert p.academic_background is None
    assert p.target_roles == []
    assert p.application is not None  # web applicant flow always creates a mock tracking record


# ---------- optional email for the notification channel ----------
def test_build_profile_collects_email_and_enables_email_channel():
    p = build_profile(_FakeForm({"email": "  Applicant@Example.COM  "}))
    assert p.email == "applicant@example.com"  # trimmed + normalised
    assert [c.value for c in p.notification_prefs.channels] == ["in_app", "email"]


def test_build_profile_without_email_keeps_in_app_only():
    p = build_profile(_FakeForm({}))
    assert p.email is None
    assert [c.value for c in p.notification_prefs.channels] == ["in_app"]


@pytest.mark.parametrize("bad", [
    "nope", "a@b", "a b@x.com", "a@@x.com", "a@x..com", "x" * 250 + "@example.com",
])
def test_build_profile_rejects_malformed_email(bad):
    with pytest.raises(ProfileFormError):
        build_profile(_FakeForm({"email": bad}))


def test_form_email_reaches_the_email_notification_channel():
    """Regression: the form collected no email, so #5 email reminders had no recipient."""
    from app.agents.tracker.reminders import dispatch_due

    sent = []

    class _SpyNotifier:
        def send(self, to, subject, body):
            sent.append(to)
            return True

    p = build_profile(_FakeForm({"email": "applicant@example.com"}))
    today = date.fromisoformat(DEFAULT_APPLICATION_DEADLINE) - timedelta(days=7)
    dispatch_due(p, today=today, notifier=_SpyNotifier())
    assert sent == ["applicant@example.com"]


# ---------- stage vocabulary: honour what was submitted, reject what is unknown ----------
@pytest.mark.parametrize("stage", ["prospect", "applicant", "admitted", "current",
                                  "graduating", "alumni"])
def test_normalize_stage_honours_every_authority_stage(stage):
    """Regression: everything except `current` used to collapse into `applicant`.

    That silently handed an alumnus an applicant's checklist, and it also made
    widening the extractor's stage whitelist inert, since the six values it newly
    accepted were flattened back to two here.
    """
    assert normalize_stage(stage).value == stage


def test_normalize_stage_defaults_only_when_nothing_was_submitted():
    # Blank is a missing form field, not a user's choice -> the UI default.
    assert normalize_stage("").value == "applicant"
    assert normalize_stage(None).value == "applicant"


def test_normalize_stage_rejects_an_unknown_stage_instead_of_defaulting():
    with pytest.raises(ProfileFormError) as err:
        normalize_stage("alumnus")          # a plausible typo for `alumni`
    assert "alumnus" in str(err.value)         # names what was rejected
    assert "alumni" in str(err.value)          # and what was accepted


def test_unknown_stage_on_advise_is_shown_as_a_form_error_not_a_500(client):
    resp = client.post("/advise", data={"lifecycle_stage": "alumnus",
                                        "degree_level": "bachelor"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "alumnus" in body
    assert "Programme comparison" not in body   # results were NOT rendered


def test_unknown_stage_on_extract_is_shown_as_a_form_error_not_a_500(client):
    resp = client.post("/extract", data={"lifecycle_stage": "alumnus", "text": "hi"})
    assert resp.status_code == 200
    assert "alumnus" in resp.get_data(as_text=True)


def test_malformed_email_is_shown_on_the_form_not_raised_as_a_server_error(client):
    """Regression: /advise called build_profile outside any try/except.

    Failing fast on a typo'd address is right, but the route let ProfileFormError
    escape, so the applicant got an unhandled 500 instead of a correction prompt.
    """
    resp = client.post("/advise", data={
        "lifecycle_stage": "applicant",
        "degree_level": "bachelor",
        "field_of_study": "computer_science",
        "work_years": "2",
        "email": "not-an-email",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "valid email address" in body          # the correction prompt is shown
    assert "not-an-email" in body                # and what they typed is preserved
    assert "Programme comparison" not in body    # results were NOT rendered


# ---------- web routes ----------
def test_landing_renders(client):
    # GET / is now the natural-language / upload landing page.
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "MSc DFT Assistant" in body and "Upload CV" in body


def test_advise_full_profile_shows_all_sections(client):
    resp = client.post("/advise", data={
        "lifecycle_stage": "applicant",
        "degree_level": "bachelor",
        "field_of_study": "computer_science",
        "work_years": "2",
        "country": "IN",
        "technical_proficiency": "intermediate",
        "finance_knowledge": "basic",
        "target_roles": ["fintech_pm"],
        "application_type": "full_time",
        "submitted_documents": ["cv"],
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Application checklist" in body
    assert "TOEFL / IELTS Score Report" in body  # checklist works (IN)
    assert "NUS MSc in Digital Financial Technology" in body  # real comparison data
    # applicants also receive #7 early planning
    assert "Post-enrolment course and career advice" in body


def test_advise_current_student_skips_applicant_sections(client):
    resp = client.post("/advise", data={
        "lifecycle_stage": "current",
        "degree_level": "bachelor",
        "field_of_study": "computer_science",
        "technical_proficiency": "intermediate",
        "finance_knowledge": "basic",
        "target_roles": ["fintech_pm"],
        "completed_modules": "BMD5301",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Course and skill direction advice" in body
    assert "Fintech Management" in body  # real recommended module (BMS5312)
    assert "Application checklist" not in body
    assert "Programme comparison" not in body


_TRACKER_SECTION_ID = "tracker"
_OPTIONAL_HEADING = "Additional materials (not blocking)"
_OPTIONAL_LABEL = "Other Supporting Documents"   # `supporting` in admissions_rules.json
_REQUIRED_LABEL = "Curriculum Vitae / CV"        # `required` in admissions_rules.json


def _section(body: str, section_id: str) -> str:
    """The rendered markup of one results.html <section>, so assertions cannot
    accidentally match the same label in another panel (material analysis and the
    #4 checklist list every document too)."""
    start = body.index(f'id="{section_id}"')
    return body[start:body.index("</section>", start)]


def test_tracker_surfaces_optional_material_without_counting_it_as_blocking(client):
    """Regression: splitting outstanding docs into required/optional dropped the
    optional ones from the web UI entirely, so nothing on the page mentioned them."""
    resp = client.post("/advise", data={
        "lifecycle_stage": "applicant",
        "degree_level": "bachelor",
        "field_of_study": "computer_science",
        "work_years": "2",
        "country": "IN",
    })  # no uploads -> DOCS_REQUIRED, with both required and optional items outstanding
    assert resp.status_code == 200
    tracker = _section(resp.get_data(as_text=True), _TRACKER_SECTION_ID)
    blocking, _, non_blocking = tracker.partition(_OPTIONAL_HEADING)

    assert non_blocking, "the tracker section never rendered the non-blocking materials block"
    assert _OPTIONAL_LABEL in non_blocking       # optional material is visible again
    assert _OPTIONAL_LABEL not in blocking       # ...but never as an outstanding requirement
    assert _REQUIRED_LABEL in blocking           # required material still blocks
    assert _REQUIRED_LABEL not in non_blocking


def test_advise_without_roles_prompts_in_recommendation(client):
    resp = client.post("/advise", data={
        "degree_level": "bachelor",
        "field_of_study": "finance",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # applicant flow now includes #7, which asks for target role when missing.
    assert "Application checklist" in body
    assert "target role" in body


def test_current_student_without_roles_prompts_in_recommendation(client):
    resp = client.post("/advise", data={
        "lifecycle_stage": "current",
        "degree_level": "bachelor",
        "field_of_study": "finance",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "target role" in body  # need_clarification message mentions it
