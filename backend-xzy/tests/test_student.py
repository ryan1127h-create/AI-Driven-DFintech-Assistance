"""Smoke tests for the student-facing web UI (no LLM key needed)."""
import pytest

from student import webapp
from student.profile_form import build_profile


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


# ---------- web routes ----------
def test_landing_renders(client):
    # GET / is now the natural-language / upload landing page.
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "申请助手" in body and "上传简历" in body


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
    assert "申请清单" in body
    assert "TOEFL / IELTS Score Report" in body  # checklist works (IN)
    assert "NUS MSc in Digital Financial Technology" in body  # real comparison data
    assert "入学后选课与职业建议" in body  # applicants also receive #7 early planning


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
    assert "选课与技能方向建议" in body
    assert "Fintech Management" in body  # real recommended module (BMS5312)
    assert "申请清单" not in body
    assert "项目对比" not in body


def test_advise_without_roles_prompts_in_recommendation(client):
    resp = client.post("/advise", data={
        "degree_level": "bachelor",
        "field_of_study": "finance",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # applicant flow now includes #7, which asks for target role when missing.
    assert "申请清单" in body
    assert "目标岗位" in body


def test_current_student_without_roles_prompts_in_recommendation(client):
    resp = client.post("/advise", data={
        "lifecycle_stage": "current",
        "degree_level": "bachelor",
        "field_of_study": "finance",
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "目标岗位" in body  # need_clarification message mentions it
