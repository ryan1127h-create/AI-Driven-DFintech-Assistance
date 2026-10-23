"""
Profile service — the rules on top of the profile schema: what the user
sees and may edit (see validation.py), validated batch edits, lifecycle
stage moves, confirming values, resolving conflicts, consents, and the
profile summary injected into chat.
"""

from __future__ import annotations

import json
from datetime import date

import psycopg

from app.core import events
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.profile import repository
from app.domains.profile.validation import (
    PROGRAMS_REF,
    ROLE_TAGS_REF,
    FieldValueError,
    drop_expired_items,
    is_displayed,
    lock_reason,
    validate_value,
)
from app.domains.program_catalog import interface as program_catalog

logger = get_logger(__name__)

CONSENT_KEYS = (
    "consent_personalized_rec",
    "consent_system_data",
    "consent_cv_processing",
    "consent_alumni_matching",
    "consent_model_improvement",
)
# Version of the privacy notice a consent decision was made under.
NOTICE_VERSION = "2026-09"
# The purposes the chat assistant serves; a field reaches the chat prompt
# if any of them may use it under the user's consents.
CHAT_PURPOSES = ("adm", "course", "career")
CONFLICT_ACTIONS = ("accept_candidate", "keep_current", "dismiss")
# Dictionary stage codes (field_definitions.stages) per lifecycle stage.
STAGE_CODES = {
    "prospect": "PRO", "applicant": "APP", "admitted": "ADM",
    "current": "CUR", "graduating": "GRD", "alumni": "ALU",
}
# Rated by the user against each level's own description; a CV can't place
# someone on these scales, so CV import never pre-fills them.
SELF_RATED_FIELDS = frozenset({
    "code_level", "math_stats_level", "finance_level", "ml_ai_level",
    "data_engineering_level", "blockchain_level",
})

_DEFINITION_KEYS = (
    "field_key", "module", "label", "value_type", "allowed_values", "value_labels",
    "values_ref", "max_items", "tier", "stages", "sources", "value_spec", "description",
)


def _role_tags() -> dict[str, str]:
    """tag -> English name of the role tags target_role_families & co.
    take their values from (owned by the knowledge domain)."""
    return {row["tag"]: row["name_en"] for row in knowledge.list_role_tags()}


def _program_options() -> dict[str, str]:
    """program id -> display name ("HKUST MSc(FinTech)") of the catalogue
    programmes competing_programs takes its values from — every one but
    MSc DFT, the programme they are compared with. Empty when the
    catalogue can't be read: the profile still loads, that field just
    offers nothing to pick."""
    try:
        programs = program_catalog.list_programs()
    except Exception:
        logger.exception("profile: reading the programme catalogue failed")
        return {}
    return {p["program_id"]: f'{p["university"]["short_name"]} {p["short_name"]}'
            for p in programs if not p["is_target"]}


def _ref_options() -> dict[str, dict[str, str]]:
    """values_ref -> {key: English display name}: the options of every
    field that takes its values from another table."""
    return {ROLE_TAGS_REF: _role_tags(), PROGRAMS_REF: _program_options()}


def _ref_keys(options: dict[str, dict[str, str]]) -> dict[str, set[str]]:
    return {ref: set(values) for ref, values in options.items()}


def _labels(definition: dict, ref_options: dict[str, dict[str, str]]) -> dict | None:
    ref = definition.get("values_ref")
    return ref_options.get(ref) if ref else definition.get("value_labels")


def _actor(user_id: str) -> str:
    return f"user:{user_id}"


def _db_message(exc: psycopg.Error) -> str:
    return (exc.diag.message_primary if exc.diag else None) or str(exc)


# --- reads ------------------------------------------------------------------

def get_profile(user_id: str) -> dict:
    """{user_id, fields: {key: {value, source, verified, updated_at,
    editable, locked_reason}}, open_conflicts} — displayed
    fields only; expired admission tests are left out."""
    definitions = repository.load_field_definitions()
    today = date.today()
    quotes = repository.list_cv_quotes(user_id)
    fields = {}
    for key, entry in repository.get_profile(user_id).items():
        definition = definitions.get(key)
        if definition is None or not is_displayed(definition):
            continue
        reason = lock_reason(definition, entry)
        fields[key] = {
            "value": drop_expired_items(entry["value"], definition, today),
            "source": entry["source"],
            "verified": entry["verified"],
            "updated_at": entry["updated_at"],
            "editable": reason is None,
            "locked_reason": reason,
            "cv_quote": quotes.get(key) if entry["source"] == "CV" else None,
        }
    return {
        "user_id": user_id,
        "fields": fields,
        "open_conflicts": len(repository.list_open_conflicts(user_id)),
    }


def get_definitions() -> dict:
    """The displayed part of the field dictionary, in dictionary order,
    each with whether it is editable when nothing is on file yet, plus the
    options (key -> display name) of each table values_ref fields choose
    from, by values_ref."""
    fields = []
    for definition in repository.load_field_definitions().values():
        if not is_displayed(definition):
            continue
        reason = lock_reason(definition, None)
        fields.append({
            **{k: definition[k] for k in _DEFINITION_KEYS},
            "editable": reason is None,
            "locked_reason": reason,
        })
    return {"fields": fields, "ref_options": _ref_options()}


def get_field(user_id: str, field_key: str):
    """The current merged value of one field, or None."""
    entry = repository.get_profile(user_id).get(field_key)
    return entry["value"] if entry else None


# --- writes -----------------------------------------------------------------

def update_fields(user_id: str, changes: dict, cv_document_id: str | None = None) -> dict:
    """Validates every change first (unknown or read-only field, bad value)
    and applies none unless all pass; then writes them in one transaction
    as the user's own (source QA). A None value deletes the field.

    With cv_document_id (answers reviewed after a CV import), a value equal
    to that document's extracted candidate is stored as source CV with its
    quote as evidence; anything the user changed stays QA. The source is
    decided here, against the stored candidates, never by the client."""
    if not changes:
        raise ValidationError("No profile fields provided.")
    definitions = repository.load_field_definitions()
    ref_keys = _ref_keys(_ref_options())
    current = repository.get_profile(user_id)

    errors, normalized = [], {}
    for key, value in changes.items():
        definition = definitions.get(key)
        if definition is None or not is_displayed(definition):
            errors.append(f"{key}: unknown field")
            continue
        reason = lock_reason(definition, current.get(key))
        if reason is not None:
            errors.append(f"{key}: read-only ({reason})")
            continue
        if value is None:
            normalized[key] = None
            continue
        try:
            normalized[key] = validate_value(key, value, definitions, ref_keys)
        except FieldValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValidationError("; ".join(errors))
    _apply_main_target_role_rule(normalized, current)
    from_cv = _cv_evidence(user_id, cv_document_id, normalized) if cv_document_id else {}

    try:
        repository.set_fields(user_id, normalized, source="QA", actor=_actor(user_id), from_cv=from_cv)
    except psycopg.errors.RaiseException as exc:
        # The field_values trigger disagreed with validate_value — report it
        # as the user's input problem it most likely is.
        raise ValidationError(_db_message(exc)) from exc
    # A CV value the user has now accepted settles any CV-vs-own-answer
    # conflict still open for that field.
    for conflict in repository.list_open_conflicts(user_id):
        if conflict["kind"] == "self_vs_cv" and conflict["field_key"] in from_cv:
            repository.close_conflict(conflict["id"], "resolved")
    events.publish(events.PROFILE_CHANGED, user_id)
    return get_profile(user_id)


def _cv_evidence(user_id: str, document_id: str, normalized: dict) -> dict[str, dict]:
    """{field_key: evidence_ref} for the changes that keep a CV candidate."""
    document = repository.get_cv_document(user_id, document_id)
    if document is None:
        raise NotFoundError("No such CV import.")
    candidates = document["candidates"] or {}
    return {
        key: {"cv_document_id": str(document_id), "quote": candidates[key]["quote"]}
        for key, value in normalized.items()
        if value is not None and key in candidates and same_value(value, candidates[key]["value"])
    }


def _canonical(value):
    if isinstance(value, list):
        return sorted(json.dumps(item, sort_keys=True) for item in value)
    return value


def same_value(a, b) -> bool:
    """Equal field values, ignoring the order of list items."""
    return _canonical(a) == _canonical(b)


def _apply_main_target_role_rule(changes: dict, current: dict) -> None:
    """main_target_role must be one of target_role_families. A main role
    being set outside them is an error; families changing so that the
    stored main role drops out clears it (added to `changes`)."""
    def _after(key):
        if key in changes:
            return changes[key]
        entry = current.get(key)
        return entry["value"] if entry else None

    families = _after("target_role_families") or []
    main = _after("main_target_role")
    if main is None or main in families:
        return
    if "main_target_role" in changes:
        raise ValidationError("main_target_role: must be one of target_role_families")
    changes["main_target_role"] = None


def set_lifecycle_stage(user_id: str, stage: str, *, source: str, actor: str) -> None:
    """Moves the user to `stage` (registration, application binding)."""
    validate_value("lifecycle_stage", stage, repository.load_field_definitions(), {})
    current = repository.get_field_value(user_id, "lifecycle_stage")
    if current is not None and current["value"] == stage:
        return
    repository.set_fields(user_id, {"lifecycle_stage": stage}, source=source, actor=actor)
    events.publish(events.PROFILE_CHANGED, user_id)


# --- conflicts --------------------------------------------------------------

def list_conflicts(user_id: str) -> list[dict]:
    definitions = repository.load_field_definitions()
    return [
        {**c, "label": definitions.get(c["field_key"], {}).get("label")}
        for c in repository.list_open_conflicts(user_id)
    ]


def resolve_conflict(user_id: str, conflict_id: int, action: str) -> dict:
    """accept_candidate: the candidate value becomes the field's value
    (verified, since the user chose it); keep_current: the stored value
    stays and is confirmed; dismiss: close without deciding."""
    if action not in CONFLICT_ACTIONS:
        raise ValidationError(f"Unknown action: {action}")
    conflict = next((c for c in repository.list_open_conflicts(user_id) if c["id"] == conflict_id), None)
    if conflict is None:
        raise NotFoundError("No such open conflict.")

    key = conflict["field_key"]
    if action == "accept_candidate":
        definitions = repository.load_field_definitions()
        value = validate_value(key, conflict["candidate_value"], definitions, _ref_keys(_ref_options()))
        source = conflict["candidate_source"] if conflict["candidate_source"] in repository.SOURCES else "QA"
        repository.set_field(user_id, key, value, source=source, actor=_actor(user_id), verified=True)
    elif action == "keep_current":
        repository.confirm_field(user_id, key, actor=_actor(user_id))
    repository.close_conflict(conflict_id, "dismissed" if action == "dismiss" else "resolved")
    if action == "accept_candidate":
        events.publish(events.PROFILE_CHANGED, user_id)
    return get_profile(user_id)


# --- CV import ----------------------------------------------------------------

_CV_TARGET_KEYS = ("field_key", "label", "value_type", "allowed_values", "value_labels", "max_items", "value_spec")


def cv_targets(user_id: str) -> list[dict]:
    """The fields a CV may pre-fill for this user: the dictionary lists CV
    as a source and extracts them literally (inferred ones such as
    total_work_years are always asked directly), they apply to the user's
    lifecycle stage, aren't self-ratings, and the user may edit them."""
    definitions = repository.load_field_definitions()
    current = repository.get_profile(user_id)
    stage_code = STAGE_CODES.get((current.get("lifecycle_stage") or {}).get("value"))
    return [
        {k: definition[k] for k in _CV_TARGET_KEYS}
        for key, definition in definitions.items()
        if "CV" in (definition["sources"] or [])
        and definition["extraction_type"] == "literal"
        and key not in SELF_RATED_FIELDS
        and (stage_code is None or stage_code in (definition["stages"] or []))
        and lock_reason(definition, current.get(key)) is None
    ]


def check_value(field_key: str, value):
    """The value normalized as the profile would store it, or None if the
    field doesn't accept it."""
    try:
        return validate_value(field_key, value, repository.load_field_definitions(), _ref_keys(_ref_options()))
    except FieldValueError:
        return None


def start_cv_document(user_id: str) -> str:
    """Records an upload; the file itself is never stored."""
    return str(repository.create_cv_document(user_id, storage_bucket=None, storage_path=None)["id"])


def fail_cv_document(document_id: str, error: str) -> None:
    repository.save_cv_result(document_id, error=error)


def finish_cv_document(user_id: str, document_id: str, candidates: dict) -> dict:
    """Stores the checked candidates ({field_key: {value, quote}}) and opens
    a self_vs_cv conflict for every field the user had already answered
    differently (once per field and candidate). Returns the import as
    cv_import_view() describes it."""
    repository.save_cv_result(document_id, candidates=candidates)
    current = repository.get_profile(user_id)
    open_conflicts = {
        (c["field_key"], json.dumps(c["candidate_value"], sort_keys=True))
        for c in repository.list_open_conflicts(user_id) if c["kind"] == "self_vs_cv"
    }
    for key, candidate in candidates.items():
        entry = current.get(key)
        if entry is None or entry["value"] in (None, [], {}) or same_value(entry["value"], candidate["value"]):
            continue
        if (key, json.dumps(candidate["value"], sort_keys=True)) in open_conflicts:
            continue
        repository.record_conflict(
            user_id, key, kind="self_vs_cv",
            current_value=entry["value"], current_source=entry["source"],
            candidate_value=candidate["value"], candidate_source="CV",
        )
    return cv_import_view(user_id, repository.get_cv_document(user_id, document_id))


def delete_cv_data(user_id: str) -> int:
    return repository.delete_cv_data(user_id)


def latest_cv_import(user_id: str) -> dict | None:
    document = repository.get_latest_cv_document(user_id)
    return cv_import_view(user_id, document) if document else None


def cv_import_view(user_id: str, document: dict) -> dict:
    """One import with each candidate compared to the profile now: "new"
    (nothing on file, so it pre-fills the questionnaire), "same", or
    "different" (left for the user to settle as a conflict)."""
    definitions = repository.load_field_definitions()
    current = repository.get_profile(user_id)
    fields = []
    candidates = document["candidates"] or {}
    for key in sorted(candidates, key=lambda k: list(definitions).index(k) if k in definitions else len(definitions)):
        candidate = candidates[key]
        entry = current.get(key)
        if entry is None or entry["value"] in (None, [], {}):
            status = "new"
        elif same_value(entry["value"], candidate["value"]):
            status = "same"
        else:
            status = "different"
        fields.append({
            "field_key": key,
            "label": definitions.get(key, {}).get("label"),
            "value": candidate["value"],
            "display": describe_value(key, candidate["value"]),
            "quote": candidate["quote"],
            "status": status,
        })
    return {
        "document_id": str(document["id"]),
        "parse_status": document["parse_status"],
        "error": document["error"],
        "uploaded_at": document["uploaded_at"],
        "parsed_at": document["parsed_at"],
        "fields": fields,
    }


# --- consents ---------------------------------------------------------------

def has_consent(user_id: str, consent_key: str) -> bool:
    return repository.has_consent(user_id, consent_key)


def missing_purpose_consent(user_id: str, purpose: str) -> str | None:
    """The consent the user still has to give before their profile can be
    used for `purpose`, or None when nothing stands in the way."""
    key = repository.purpose_consent_key(purpose)
    return key if key and not repository.has_consent(user_id, key) else None


def get_consents(user_id: str) -> list[dict]:
    """All consent keys, not-granted unless the latest decision granted."""
    definitions = repository.load_field_definitions()
    current = repository.get_current_consents(user_id)
    return [
        {
            "key": key,
            "label": definitions.get(key, {}).get("label"),
            "description": definitions.get(key, {}).get("description"),
            "granted": bool(current.get(key, {}).get("granted")),
            "updated_at": current.get(key, {}).get("created_at"),
        }
        for key in CONSENT_KEYS
    ]


def update_consents(user_id: str, decisions: dict[str, bool]) -> list[dict]:
    """Records a new decision for each key whose value actually changes
    (or was never decided); the history is append-only."""
    unknown = set(decisions) - set(CONSENT_KEYS)
    if unknown:
        raise ValidationError(f"Unknown consent keys: {sorted(unknown)}")
    current = repository.get_current_consents(user_id)
    for key, granted in decisions.items():
        if key in current and bool(current[key]["granted"]) == granted:
            continue
        repository.record_consent(user_id, key, granted, notice_version=NOTICE_VERSION)
    return get_consents(user_id)


# --- facts for specialist agents ------------------------------------------------

def get_facts_for_purpose(user_id: str, purpose: str) -> dict:
    """{field_key: value} a specialist may use for `purpose` (course,
    career, adm, ...): consent-filtered like the chat summary, expired
    admission tests left out. Empty without consent or profile."""
    definitions = repository.load_field_definitions()
    today = date.today()
    facts = {}
    for key, entry in repository.get_profile_for_purpose(user_id, purpose).items():
        definition = definitions.get(key)
        if definition is None:
            continue
        value = drop_expired_items(entry["value"], definition, today)
        if value not in (None, [], {}):
            facts[key] = value
    return facts


def get_fact_sources_for_purpose(user_id: str, purpose: str) -> dict[str, str]:
    """{field_key: source} for the facts get_facts_for_purpose() returns."""
    facts = get_facts_for_purpose(user_id, purpose)
    entries = repository.get_profile_for_purpose(user_id, purpose)
    return {key: entries[key]["source"] for key in facts if key in entries}


def describe_value(field_key: str, value) -> str:
    """A field value as English display text (option labels, the names
    of role tags and programmes), e.g. code_level 3 -> "Has built a
    complete project with tests"."""
    definition = repository.load_field_definitions().get(field_key) or {}
    return _display(value, _labels(definition, _ref_options()))


def field_labels(field_keys) -> dict[str, str]:
    """field_key -> its English label, for the keys the dictionary holds."""
    definitions = repository.load_field_definitions()
    return {key: definitions[key]["label"] for key in field_keys if key in definitions}


def describe_facts(facts: dict) -> list[str]:
    """One "Label: value" line per fact, in field-dictionary order."""
    definitions = repository.load_field_definitions()
    return [
        f"{definition['label']}: {describe_value(key, facts[key])}"
        for key, definition in definitions.items() if key in facts
    ]


def _display(value, labels: dict | None) -> str:
    if isinstance(value, list):
        return ", ".join(_display(v, labels) for v in value)
    if isinstance(value, dict):
        if "course_code" in value:
            return value["course_code"]
        if "key" in value:
            # e.g. a test score or a certification level: "GRE 325", "CFA L2"
            extras = [str(value[k]) for k in ("score", "level") if value.get(k) not in (None, "")]
            return " ".join([_display(value["key"], labels), *extras])
        return json.dumps(value, ensure_ascii=False)
    if labels and str(value) in labels:
        return labels[str(value)]
    return str(value)


# --- chat summary -----------------------------------------------------------

def _format_value(key: str, value, labels: dict | None) -> str:
    if key == "application_record" and isinstance(value, list):
        parts = []
        for app in value:
            missing = [str(item).replace("_", " ") for item in app.get("missing_items") or []]
            term = f" ({app['admission_term']})" if app.get("admission_term") else ""
            text = f"{app.get('application_no')}{term}: {app.get('status')}"
            parts.append(text + (f", documents not yet received: {', '.join(missing)}" if missing else ""))
        return "; ".join(parts)
    if key == "admission_tests" and isinstance(value, list):
        return ", ".join(
            f"{t.get('key')} {t.get('score')}" + (f" ({t['test_date']})" if t.get("test_date") else "")
            for t in value if isinstance(t, dict)
        )
    if isinstance(value, list):
        return ", ".join(_format_value(key, v, labels) for v in value)
    if isinstance(value, dict):
        if "course_code" in value:
            return value["course_code"]
        if "key" in value:
            extra = ", ".join(f"{k}={v}" for k, v in value.items() if k != "key")
            return _format_value(key, value["key"], labels) + (f" ({extra})" if extra else "")
        return json.dumps(value, ensure_ascii=False)
    if labels and str(value) in labels:
        return f"{labels[str(value)]} ({value})"
    return str(value)


def chat_summary_text(user_id: str) -> str:
    """The user's profile as one "label (key): value" line per field, in
    dictionary order: lifecycle_stage always, everything else only if a
    chat purpose may use it under the user's consents. Empty string if
    there is nothing to say."""
    definitions = repository.load_field_definitions()
    profile = repository.get_profile(user_id)
    if not profile:
        return ""
    allowed = {"lifecycle_stage"}
    for purpose in CHAT_PURPOSES:
        allowed |= set(repository.get_profile_for_purpose(user_id, purpose))

    today = date.today()
    ref_options = _ref_options()
    lines = []
    for key, definition in definitions.items():
        entry = profile.get(key)
        if entry is None or key not in allowed:
            continue
        value = drop_expired_items(entry["value"], definition, today)
        if value in (None, [], {}):
            continue
        line = f"- {definition['label']} ({key}): {_format_value(key, value, _labels(definition, ref_options))}"
        lines.append(line)
    notes = derived_course_notes(user_id)
    lines.extend(f"- {note}" for note in notes["readiness"] + notes["graduation"])
    if not lines:
        return ""
    return "Known user profile (use it but don't recite it verbatim):\n" + "\n".join(lines)


# --- derived labels ---------------------------------------------------------------
# Computed by app.domains.derived_labels from the profile, school records
# and the curriculum; stored here, never shown to the user.

_AREA_NAMES = {"programming": "programming", "maths_stats": "maths and statistics", "finance": "finance"}


def get_profile_values(user_id: str) -> dict:
    """{field_key: value} across answers and school records, unfiltered —
    for the derived-label rules only, never for anything shown or sent to
    the assistant (that goes through the consent-filtered reads)."""
    return {key: entry["value"] for key, entry in repository.get_profile(user_id).items()}


def save_derived_labels(user_id: str, labels: dict, rules_version: str) -> None:
    repository.save_derived(user_id, labels, rules_version=rules_version)


def get_derived_labels(user_id: str) -> dict | None:
    return repository.get_derived(user_id)


def list_user_ids() -> list[str]:
    return repository.list_user_ids()


def derived_course_notes(user_id: str) -> dict[str, list[str]]:
    """{"readiness": [...], "graduation": [...]}: readiness gaps and
    graduation risks as plain sentences, for course advice — only with the
    personalised-recommendations consent, the same consent the course
    purpose's profile facts need (both lists empty without it)."""
    notes = {"readiness": [], "graduation": []}
    if not repository.has_consent(user_id, "consent_personalized_rec"):
        return notes
    derived = repository.get_derived(user_id) or {}
    for area, gap in (derived.get("readiness_gap") or {}).items():
        if gap.get("status") == "gap":
            notes["readiness"].append(
                f"Readiness gap (derived): {_AREA_NAMES.get(area, area)} self-rated at level {gap['level']}, "
                f"below the level {gap['required']} the programme expects"
            )
    for risk in derived.get("graduation_risk_flags") or []:
        notes["graduation"].append(f"Graduation risk (derived): {risk['message']}")
    return notes


def derived_readiness_gaps(user_id: str) -> list[dict]:
    """[{area, level, required}] for each programme-readiness area the user
    is self-rated below, for career planning — under the same consent as
    derived_course_notes (empty without it)."""
    if not repository.has_consent(user_id, "consent_personalized_rec"):
        return []
    derived = repository.get_derived(user_id) or {}
    return [
        {"area": area, "level": gap["level"], "required": gap["required"]}
        for area, gap in (derived.get("readiness_gap") or {}).items()
        if gap.get("status") == "gap"
    ]
