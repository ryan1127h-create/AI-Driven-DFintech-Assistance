"""Flask web UI for the admin authoring tool.

Reuses the existing pipeline (registry / extract / schemas / audit / apply_draft).
The runtime agents are untouched. Two-step human-approval flow:

    GET  /          edit form
    POST /generate  -> DeepSeek draft -> validate -> diff -> review page
    POST /apply      -> apply_draft (write + archive + audit) -> result page

Run: python -m admin.webapp   (serves http://127.0.0.1:5000)
"""
from __future__ import annotations

import json

from flask import Flask, redirect, render_template, request, url_for

from pathlib import Path

from common import config

from . import audit, schemas
from .author import apply_draft, rollback
from .registry import all_target_names, get_target

_ASSETS = str(Path(__file__).resolve().parents[1] / "webassets")
app = Flask(__name__, static_folder=_ASSETS, static_url_path="/static")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/")
def index():
    targets = [get_target(n) for n in all_target_names()]
    return render_template("index.html", targets=targets)


@app.post("/generate")
def generate():
    target_name = request.form.get("target", "")
    admin = request.form.get("admin", "").strip() or "unknown"
    instruction = request.form.get("instruction", "").strip()

    try:
        target = get_target(target_name)
    except KeyError:
        return render_template("result.html", error=f"Unknown data type: {target_name}"), 400
    if not instruction:
        return redirect(url_for("index"))

    current = _read_json(target.file_path)

    # The only LLM-dependent step.
    from .extract import ExtractionError, extract

    try:
        draft = extract(target, current, instruction)
    except ExtractionError as e:
        return render_template(
            "review.html", target=target, admin=admin, instruction=instruction,
            error=str(e), changes=None, draft_json=None,
        )

    ok, err = schemas.validate_draft(target.schema, draft)
    if not ok:
        return render_template(
            "review.html", target=target, admin=admin, instruction=instruction,
            error=f"Draft validation failed; cannot write:\n{err}", changes=None, draft_json=None,
        )

    changes = audit.compute_diff(current, draft)
    return render_template(
        "review.html",
        target=target, admin=admin, instruction=instruction, error=None,
        changes=changes,
        draft_json=json.dumps(draft, ensure_ascii=False),
        draft_pretty=json.dumps(draft, ensure_ascii=False, indent=2),
    )


@app.post("/apply")
def apply():
    target_name = request.form.get("target", "")
    admin = request.form.get("admin", "unknown")
    instruction = request.form.get("instruction", "")
    draft_json = request.form.get("draft_json", "")

    try:
        target = get_target(target_name)
        draft = json.loads(draft_json)
    except (KeyError, json.JSONDecodeError) as e:
        return render_template("result.html", error=f"Invalid request: {e}"), 400

    # apply_draft re-validates and re-diffs (don't trust the hidden field).
    # Clicking "Confirm and write" is the human approval.
    result = apply_draft(target, draft, instruction, admin, approver=lambda c: True)
    return render_template("result.html", result=result, target=target, error=None)


@app.get("/history")
def history():
    records = audit.read_audit_log()
    targets = []
    for name in all_target_names():
        t = get_target(name)
        targets.append({
            "name": t.name,
            "risk": t.risk,
            "versions": audit.list_versions(t.file_path.stem),
        })
    return render_template("history.html", records=records, targets=targets)


@app.post("/rollback")
def do_rollback():
    target_name = request.form.get("target", "")
    admin = request.form.get("admin", "").strip() or "unknown"
    version_name = request.form.get("version", "")
    try:
        target = get_target(target_name)
    except KeyError:
        return render_template("result.html", error=f"Unknown data type: {target_name}"), 400

    # Resolve the version strictly inside the versions dir (name only, no paths).
    versions_dir = target.file_path.parent / "_versions"
    version_path = versions_dir / Path(version_name).name

    result = rollback(target, version_path, admin)
    return render_template("result.html", result=result, target=target, error=None)


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
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
