"""Student-facing web UI (separate from the admin app).

Input flow: natural language or uploaded CV (Word/PDF) -> DeepSeek extracts a
profile -> student reviews/edits a pre-filled form -> agents run.

Runs the three profile-driven agents (#4 checklist, #6 comparison, #7
course/career) via the existing supervisor. No admin tools are exposed here.
The /advise step works without a DeepSeek key; the /extract step needs one.

Run: python -m student.webapp   (serves http://127.0.0.1:5001)
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from flask import Flask, render_template, request, send_from_directory, abort

from common import config
from supervisor import default_intents_for, route

from . import profile_form as pf
from .extract_profile import ProfileExtractionError, extract_fields, parse_file

_ASSETS = str(Path(__file__).resolve().parents[1] / "webassets")
app = Flask(__name__, static_folder=_ASSETS, static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # allow multiple uploaded materials
_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "instance" / "uploads"

_SECTION_KEYS = {
    "generate_application_checklist": "checklist",
    "get_application_status": "tracker",
    "compare_programs": "comparison",
    "recommend_courses": "recommendation",
    "recommend_career_path": "career",
}


def _form_options() -> dict:
    return dict(
        degree_levels=pf.DEGREE_LEVELS,
        fields=pf.FIELDS_OF_STUDY,
        proficiencies=pf.PROFICIENCIES,
        application_types=pf.APPLICATION_TYPES,
        stages=pf.LIFECYCLE_STAGES,
        roles=pf.TARGET_ROLES,
        materials=pf.APPLICATION_MATERIALS,
        material_name=pf.material_name,
    )


@app.get("/")
def index():
    return render_template("landing.html")


@app.post("/extract")
def extract():
    selected_stage = pf.normalize_stage(request.form.get("lifecycle_stage", "applicant")).value
    text = (request.form.get("text") or "").strip()
    upload = request.files.get("cv")

    # Prefer an uploaded file; fall back to pasted text. If neither is provided,
    # continue with a blank editable form so users can enter details manually.
    try:
        if upload and upload.filename:
            text = parse_file(upload.filename, upload.read())
        prefill = extract_fields(text) if text else {}
    except ProfileExtractionError as e:
        # Parsing errors should be shown immediately. LLM/config errors should
        # not block the demo; continue with a blank form and let the user fill
        # fields manually.
        msg = str(e)
        if "DeepSeek" not in msg and "API key" not in msg:
            return render_template("landing.html", error=msg, selected_stage=selected_stage)
        prefill = {"_notice": msg}
    prefill["lifecycle_stage"] = selected_stage

    return render_template("form.html", prefill=prefill, selected_stage=selected_stage, **_form_options())


_PRIORITY_WEIGHTS = {
    "role_fit": {"role_fit": 1.0},
    "cost": {"cost": 0.7, "role_fit": 0.3},
    "duration": {"duration": 0.7, "role_fit": 0.3},
}


@app.post("/advise")
def advise():
    selected_stage = pf.normalize_stage(request.form.get("lifecycle_stage", "applicant"))
    upload_token = uuid4().hex
    material_analysis = pf.analyse_uploaded_materials(request.files, selected_stage, save_dir=_UPLOAD_ROOT, token=upload_token)
    profile = pf.build_profile(request.form, request.files, material_results=material_analysis)
    material_summary = pf.material_summary(material_analysis) if material_analysis else None
    priorities = _PRIORITY_WEIGHTS.get(request.form.get("priority", "role_fit"))
    slots = {
        "compare_programs": {"priorities": priorities},
        "get_application_status": {},
        "recommend_courses": {},
        "recommend_career_path": {},
    }
    results = {}
    for intent in default_intents_for(profile):
        results[_SECTION_KEYS[intent]] = route(intent, profile, slots.get(intent))
    return render_template(
        "results.html",
        profile=profile,
        r=results,
        material_analysis=material_analysis,
        material_summary=material_summary,
    )


@app.get("/uploads/<token>/<path:filename>")
def view_upload(token: str, filename: str):
    """Serve files saved for this demo submission so applicants can review them."""
    folder = (_UPLOAD_ROOT / token).resolve()
    root = _UPLOAD_ROOT.resolve()
    if not str(folder).startswith(str(root)) or not folder.exists():
        abort(404)
    return send_from_directory(folder, filename, as_attachment=False)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    message = None
    ok = None
    if request.method == "POST":
        action = request.form.get("action", "save")
        key = request.form.get("api_key", "").strip()
        model = request.form.get("model", "").strip()
        if action == "save":
            config.set_credentials(api_key=key or None, model=model or None)
            ok, message = True, "Saved."
        elif action == "test":
            if key or model:
                config.set_credentials(api_key=key or None, model=model or None)
            ok, message = config.test_connection()
    return render_template("settings.html", status=config.status(), message=message, ok=ok)


def main() -> None:
    app.run(host="127.0.0.1", port=5001, debug=False)


if __name__ == "__main__":
    main()
