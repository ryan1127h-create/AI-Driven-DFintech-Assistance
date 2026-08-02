"""Build a UserProfile from student web-form input.

The student UI intentionally supports only two visible flows for the MVP:
applicant and current student.  Other lifecycle stages remain in the backend
schema for future teammates, but they are not shown in the student-facing form.

For applicants, uploaded application materials are converted into the
Application.submitted_documents/document_status fields so the #4/#5 agents can
make decisions from actual uploads rather than checkboxes.

An optional email address is validated here and carried on the profile so #5's
existing email notification channel has a recipient to send reminders to.
"""
from __future__ import annotations

import os
import re
from dotenv import load_dotenv
from datetime import date
from pathlib import Path
from dataclasses import dataclass

from werkzeug.utils import secure_filename

from common.profile import (
    AcademicBackground,
    Application,
    ApplicationType,
    ConsentFlags,
    DegreeLevel,
    DocStatus,
    FieldOfStudy,
    LifecycleStage,
    NotificationChannel,
    NotificationPrefs,
    Proficiency,
    StatusCode,
    TargetRole,
    UserProfile,
)


load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Field metadata for rendering the form (label + options).
DEGREE_LEVELS = [e.value for e in DegreeLevel]
FIELDS_OF_STUDY = [e.value for e in FieldOfStudy]
PROFICIENCIES = [e.value for e in Proficiency]
APPLICATION_TYPES = [e.value for e in ApplicationType]
# Keep only the two flows requested for the student-facing MVP.
LIFECYCLE_STAGES = [LifecycleStage.applicant.value, LifecycleStage.current.value]
TARGET_ROLES = [e.value for e in TargetRole]

# Based on NUS MSc DFinTech online submission checklist.  The demo accepts Word
# and images in addition to PDF to make upload testing convenient, but the UI
# reminds applicants that the real Graduate Admission System requires PDF files.
APPLICATION_MATERIALS: list[dict[str, str]] = [
    {
        "key": "personal_statement",
        "label": "Personal Statement",
        "hint": "Explains reasons for applying, preparation, career plans, and relevant background.",
        "required": "required",
    },
    {
        "key": "cv",
        "label": "Curriculum Vitae / CV",
        "hint": "Summarises education, internships/work experience, projects, achievements, and skills.",
        "required": "required",
    },
    {
        "key": "proof_of_residence",
        "label": "Proof of Residence / Passport / NRIC",
        "hint": "Singapore Citizens/PRs should upload both sides of NRIC; international applicants should upload passport and relevant passes.",
        "required": "required",
    },
    {
        "key": "degree_certificate",
        "label": "Official Degree Certificate / Expected Graduation Letter",
        "hint": "Graduates should upload the degree certificate; final-year students should upload expected graduation or completion proof.",
        "required": "required",
    },
    {
        "key": "transcript",
        "label": "Official Transcript(s)",
        "hint": "Complete transcript showing grades for all courses; exchange transcripts should also be provided where applicable.",
        "required": "required",
    },
    {
        "key": "english_proficiency",
        "label": "TOEFL / IELTS Score Report",
        "hint": "Required if prior university education was not mainly taught in English.",
        "required": "conditional",
    },
    {
        "key": "standardised_test_scores",
        "label": "GRE / GMAT / GATE Score Report",
        "hint": "Official notes state that GMAT/GRE is not mandatory; scores may be uploaded as supporting evidence if available.",
        "required": "supporting",
    },
    {
        "key": "referee_reports",
        "label": "Two Referee Reports / Referee Submission Evidence",
        "hint": "In the real system, referee emails are entered and referees submit online; here you may upload a confirmation screenshot or note.",
        "required": "required",
    },
    {
        "key": "financial_support",
        "label": "Financial Support Document",
        "hint": "Bank statements, payslips, or sponsor letter as financial support evidence.",
        "required": "supporting",
    },
    {
        "key": "application_fee",
        "label": "Application Fee Payment Proof",
        "hint": "S$109 application fee payment screenshot or receipt; the real system relies on payment status.",
        "required": "required",
    },
    {
        "key": "other_supporting_documents",
        "label": "Other Supporting Documents",
        "hint": "Awards, professional certificates, or other relevant evidence where applicable.",
        "required": "supporting",
    },
]
COMMON_DOCS = [m["key"] for m in APPLICATION_MATERIALS]

MATERIAL_PREFIX = "material_"
ALLOWED_MATERIAL_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg"}
MAX_MATERIAL_BYTES = 10 * 1024 * 1024
DEFAULT_APPLICATION_DEADLINE = "2026-01-31"

# Optional contact address for the existing email notification channel.
MAX_EMAIL_LENGTH = 254  # RFC 5321 practical maximum for a forward path
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
EMAIL_ERROR_MESSAGE = (
    "Please enter a valid email address (for example name@example.com), "
    "or leave the field blank to skip email reminders."
)


class ProfileFormError(ValueError):
    """Invalid student form input; the message is safe to show to the user."""


@dataclass
class UploadedMaterial:
    key: str
    label: str
    filename: str | None
    status: str  # submitted | missing | rejected
    reason: str
    size_bytes: int = 0
    view_url: str | None = None
    required: str = "required"


def _enum_or_none(enum_cls, raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        return None


def _int_or_none(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_email(raw: str | None) -> str | None:
    """Optional email address. Blank -> None; malformed -> ProfileFormError.

    Fails fast instead of silently dropping the value: a typo'd address would
    otherwise leave the applicant believing email reminders are enabled.
    """
    email = (raw or "").strip()
    if not email:
        return None
    if len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email):
        raise ProfileFormError(EMAIL_ERROR_MESSAGE)
    return email.lower()


def notification_prefs_for(email: str | None) -> NotificationPrefs:
    """Enable the existing email channel only when an address was supplied."""
    channels = [NotificationChannel.in_app]
    if email:
        channels.append(NotificationChannel.email)
    return NotificationPrefs(channels=channels)


def _getlist(form, key: str) -> list[str]:
    getlist = getattr(form, "getlist", lambda k: [])
    v = getlist(key)
    return v if isinstance(v, list) else [v]


def normalize_stage(raw: str | None) -> LifecycleStage:
    """Resolve a submitted stage against the authority vocabulary.

    Blank means "not supplied": the two-option UI submits applicant or current,
    so a missing value is a form default rather than a user's choice.

    A value the authority recognises is honoured AS GIVEN. Collapsing `alumni` or
    `graduating` into `applicant` -- which this function used to do for every
    value except `current` -- hands them an applicant's document checklist and
    silently discards what the caller actually said. It also made widening the
    extractor's stage whitelist inert, because everything it newly accepted was
    flattened again here.

    An unrecognised value raises for the same reason: a mistyped `alumnus` must
    not become a confident wrong answer.
    """
    text = (raw or "").strip()
    if not text:
        return LifecycleStage.applicant
    try:
        return LifecycleStage(text)
    except ValueError:
        accepted = ", ".join(s.value for s in LifecycleStage)
        raise ProfileFormError(
            f"Unknown profile stage {text!r}. Accepted values: {accepted}."
        ) from None


def material_name(key: str) -> str:
    return f"{MATERIAL_PREFIX}{key}"


def analyse_uploaded_materials(files, stage: LifecycleStage, save_dir: str | Path | None = None,
                               token: str | None = None) -> list[UploadedMaterial]:
    """Turn material file inputs into evidence objects and optionally persist them.

    The MVP checks presence, extension and size.  Saved files are exposed through
    /uploads/<token>/<filename> so applicants can click and review what they uploaded.
    """
    if stage != LifecycleStage.applicant:
        return []
    files = files or {}
    results: list[UploadedMaterial] = []
    base = Path(save_dir) if save_dir else None
    if base and token:
        (base / token).mkdir(parents=True, exist_ok=True)
    for spec in APPLICATION_MATERIALS:
        key = spec["key"]
        label = spec["label"]
        required = spec.get("required", "required")
        # upload = files.get(material_name(key)) if hasattr(files, "get") else None
        upload = files.get(material_name(key)) if hasattr(files, "get") else None

        if upload and not hasattr(upload, "file"):
            upload = None   # ✅ ensure it's actually a file

        filename = getattr(upload, "filename", "") or ""
        if not filename:
            results.append(UploadedMaterial(key, label, None, "missing", "Not uploaded", required=required))
            continue
        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_MATERIAL_EXTENSIONS:
            results.append(
                UploadedMaterial(key, label, filename, "rejected", f"File format {ext or '(no extension)'} is not supported", required=required)
            )
            continue
        size = 0
        # stream = getattr(upload, "stream", None)
        # if stream is not None:
        #     pos = stream.tell()
        #     stream.seek(0, os.SEEK_END)
        #     size = stream.tell()
        #     stream.seek(pos)
        file_obj = getattr(upload, "file", None)

        size = 0
        if file_obj:
            pos = file_obj.tell()
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(pos)
        if size > MAX_MATERIAL_BYTES:
            results.append(
                UploadedMaterial(key, label, filename, "rejected", "File exceeds 10MB", required=required)
            )
            continue
        # view_url = None
        # if base and token:
        #     safe = secure_filename(filename) or f"{key}{ext}"
        #     stored_name = f"{key}__{safe}"
        #     target = base / token / stored_name
        #     try:
        #         if stream is not None:
        #             stream.seek(0)
        #         upload.save(target)
        #         if stream is not None:
        #             stream.seek(0)
        #         view_url = f"/uploads/{token}/{stored_name}"
        #     except Exception as exc:  # keep the UI honest if persistence fails
        #         results.append(UploadedMaterial(key, label, filename, "rejected", f"File save failed: {exc}", size, required=required))
        #         continue
        view_url = None
        if base and token:
            safe = secure_filename(filename) or f"{key}{ext}"
            stored_name = f"{key}__{safe}"
            target = base / token / stored_name

            try:
                import shutil

                # file_obj = getattr(upload, "file", None)

                if file_obj:
                    file_obj.seek(0)
                    with open(target, "wb") as buffer:
                        shutil.copyfileobj(file_obj, buffer)
                    file_obj.seek(0)

                # view_url = f"/uploads/{token}/{stored_name}"
                view_url = f"{BASE_URL}/uploads/{token}/{stored_name}"

            except Exception as exc:
                results.append(
                    UploadedMaterial(
                        key, label, filename, "rejected",
                        f"File save failed: {exc}",
                        size,
                        required=required
                    )
                )
                continue
        results.append(UploadedMaterial(key, label, filename, "submitted", "Uploaded; click to view", size, view_url=view_url, required=required))
    return results


def required_material_keys() -> set[str]:
    return {m["key"] for m in APPLICATION_MATERIALS if m.get("required") == "required"}


def material_summary(materials: list[UploadedMaterial]) -> dict:
    required = [m for m in materials if m.required == "required"]
    submitted = [m for m in required if m.status == "submitted"]
    missing = [m for m in required if m.status == "missing"]
    rejected = [m for m in required if m.status == "rejected"]
    return {
        "required_total": len(required),
        "submitted_required": len(submitted),
        "missing_required": len(missing),
        "rejected_required": len(rejected),
        "is_complete": bool(required) and not missing and not rejected,
    }


def build_profile(form, files=None, material_results: list[UploadedMaterial] | None = None) -> UserProfile:
    """form: Flask request.form-like mapping. files: optional request.files."""
    stage = normalize_stage(form.get("lifecycle_stage", ""))
    email = parse_email(form.get("email", ""))

    degree = _enum_or_none(DegreeLevel, form.get("degree_level", ""))
    field = _enum_or_none(FieldOfStudy, form.get("field_of_study", ""))
    academic = None
    if degree and field:
        academic = AcademicBackground(degree_level=degree, field_of_study=field)

    roles = []
    for r in _getlist(form, "target_roles"):
        role = _enum_or_none(TargetRole, r)
        if role:
            roles.append(role)

    completed_modules_raw = form.get("completed_modules", "") or ""
    completed_modules = [
        code.strip().upper()
        for code in completed_modules_raw.replace(";", ",").split(",")
        if code.strip()
    ]

    # Applicants: uploaded files are the source of truth for submitted materials.
    # Backward-compatible checkbox support is retained for tests/CLI demos.
    application = None
    if stage == LifecycleStage.applicant:
        material_results = material_results if material_results is not None else analyse_uploaded_materials(files, stage)
        uploaded = [m.key for m in material_results if m.status == "submitted"]
        rejected = [m.key for m in material_results if m.status == "rejected"]
        legacy_submitted = [d for d in _getlist(form, "submitted_documents") if d in COMMON_DOCS]
        submitted = sorted(set(uploaded + legacy_submitted))
        doc_status = {d: DocStatus.submitted for d in submitted}
        doc_status.update({d: DocStatus.rejected for d in rejected})
        required_keys = required_material_keys()
        required_ok = required_keys.issubset(set(submitted)) and not (required_keys & set(rejected))
        status_code = StatusCode.SUBMITTED if required_ok else StatusCode.DOCS_REQUIRED
        # Always create a mock application for the applicant web flow so #5 can
        # explain the status and outstanding items.  This is not the real NUS
        # Graduate Admission System status.
        application = Application(
            application_id="student_web_mock",
            status_code=status_code,
            submitted_documents=submitted,
            document_status=doc_status,
            deadlines={"application_deadline": DEFAULT_APPLICATION_DEADLINE},
            status_history=[
                {"status_code": StatusCode.SUBMITTED, "date": date.today().isoformat(), "note": "Demo submission created from uploaded materials"},
                {"status_code": status_code, "date": date.today().isoformat(), "note": "Mock admissions status generated by the capstone demo"},
            ],
        )

    return UserProfile(
        user_id="student_web",
        lifecycle_stage=stage,
        authenticated=True,
        email=email,
        academic_background=academic,
        # Current students do not need these fields for #7, so ignore if posted.
        work_years=_int_or_none(form.get("work_years", "")) if stage == LifecycleStage.applicant else None,
        country=(form.get("country", "").strip().upper() or None) if stage == LifecycleStage.applicant else None,
        technical_proficiency=_enum_or_none(Proficiency, form.get("technical_proficiency", "")),
        finance_knowledge=_enum_or_none(Proficiency, form.get("finance_knowledge", "")),
        target_roles=roles,
        application_type=_enum_or_none(ApplicationType, form.get("application_type", "")) if stage == LifecycleStage.applicant else None,
        completed_modules=completed_modules,
        application=application,
        consent_flags=ConsentFlags(personalization=True, reminders=True),
        notification_prefs=notification_prefs_for(email),
    )
