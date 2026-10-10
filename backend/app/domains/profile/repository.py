"""
User profile repository — pure data access (no LLM calls, no business
rules such as which source wins a conflict; those belong in service.py).

How the `profile` schema fits together:
  - field_definitions: the dictionary of every profile field (value type,
    allowed values, which purposes may use it, and `storage` — where its
    value lives). Only fields with storage='value' are written to
    field_values; the others are owned by sis/account/consent/derived.
  - field_values: current value per (user, field). A trigger validates the
    value against its definition and stamps updated_at.
  - field_events: append-only history — every write below records one.
  - v_profile: the merged read view — field_values plus facts folded in
    from sis (academic record, enrollments, applications), with sis
    winning over self-reported values for the same field.
  - fields_for_purpose(): v_profile filtered by the user's consents for
    one purpose (adm/course/career/alumni/ops).
  - consent_events: append-only; v_consents_current is the latest per key.

Every user_id must already have a profile.profiles row, which the
auth.users insert trigger creates alongside the account.
"""

from __future__ import annotations

import json
import threading

from app.adapters.profile_db_adapter import profile_db


# --- profile schema ---------------------------------------------------------

SOURCES = ("CV", "QA", "DB", "DER", "BHV")
EXTRACTIONS = ("literal", "inferred")
PURPOSES = ("adm", "course", "career", "alumni", "ops")
CONFLICT_KINDS = ("self_vs_cv", "over_time", "source_priority")
CONFLICT_RESOLUTIONS = ("resolved", "dismissed")
CV_PARSE_STATUSES = ("pending", "parsed", "failed")

_DEFINITION_COLUMNS = (
    "field_key", "module", "label", "value_type", "allowed_values", "value_labels",
    "values_ref", "max_items", "tier", "tier_condition", "sources", "layer",
    "extraction_type", "purpose_tags", "stages", "expiry_rule", "storage",
    "user_visible", "value_spec", "description", "schema_version",
)
_VALUE_COLUMNS = (
    "field_key", "value", "source", "extraction", "verified", "evidence_ref",
    "updated_at", "expires_at",
)
_PROFILE_COLUMNS = ("field_key", "value", "source", "verified", "updated_at")
_DERIVED_COLUMNS = (
    "profile_usability", "motivation_segment", "readiness_gap", "drop_off_risk",
    "graduation_risk_flags", "engagement_score",
)
_DERIVED_JSON_COLUMNS = {"readiness_gap", "graduation_risk_flags"}

_definitions: dict[str, dict] | None = None
_definitions_lock = threading.Lock()


def _json(value) -> str | None:
    return None if value is None else json.dumps(value)


# field dictionary

def load_field_definitions() -> dict[str, dict]:
    """field_key -> definition. The dictionary only changes with a schema
    migration, so it is read once per process; call
    reload_field_definitions() after changing it."""
    global _definitions
    if _definitions is None:
        with _definitions_lock:
            if _definitions is None:
                rows = profile_db.fetch_all_dict(
                    f"select {', '.join(_DEFINITION_COLUMNS)} from profile.field_definitions order by module, field_key"
                )
                _definitions = {r["field_key"]: r for r in rows}
    return _definitions


def reload_field_definitions() -> dict[str, dict]:
    global _definitions
    with _definitions_lock:
        _definitions = None
    return load_field_definitions()


# reads

def get_profile(user_id: str) -> dict[str, dict]:
    """field_key -> {value, source, verified, updated_at},
    merged across field_values and sis (see v_profile). Empty dict if the
    user has nothing on file."""
    rows = profile_db.fetch_all_dict(
        f"select {', '.join(_PROFILE_COLUMNS)} from profile.v_profile where user_id = %s",
        (user_id,),
    )
    return {r.pop("field_key"): r for r in rows}


def get_profile_for_purpose(user_id: str, purpose: str) -> dict[str, dict]:
    """Same shape as get_profile(), limited to the fields this purpose may
    use and that the user's consents allow (see fields_for_purpose())."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose: {purpose}")
    rows = profile_db.fetch_all_dict(
        f"select {', '.join(_PROFILE_COLUMNS)} from profile.fields_for_purpose(%s, %s)",
        (user_id, purpose),
    )
    return {r.pop("field_key"): r for r in rows}


def get_field_value(user_id: str, field_key: str) -> dict | None:
    """The stored field_values row itself (including an expired one), not
    the merged view — for callers that need extraction/evidence_ref/
    expires_at."""
    return profile_db.fetch_one_dict(
        f"select {', '.join(_VALUE_COLUMNS)} from profile.field_values where user_id = %s and field_key = %s",
        (user_id, field_key),
    )


def list_field_events(user_id: str, field_key: str | None = None, limit: int = 100) -> list[dict]:
    """Newest first."""
    where, params = "user_id = %s", [user_id]
    if field_key is not None:
        where += " and field_key = %s"
        params.append(field_key)
    return profile_db.fetch_all_dict(
        f"""
        select id, field_key, action, old_value, new_value, source, actor, created_at
          from profile.field_events
         where {where}
         order by created_at desc, id desc
         limit %s
        """,
        [*params, limit],
    )


# writes — each one updates field_values and appends its field_events row
# in the same transaction

def _insert_event(tx, user_id, field_key, action, old_value, new_value, source, actor) -> None:
    tx.execute(
        """
        insert into profile.field_events
            (user_id, field_key, action, old_value, new_value, source, actor)
        values (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
        """,
        (user_id, field_key, action, _json(old_value), _json(new_value), source, actor),
    )


def _upsert_in_tx(tx, user_id, field_key, value, source, actor,
                  extraction=None, evidence_ref=None, verified=False, expires_at=None) -> dict:
    old = tx.fetch_one(
        "select value from profile.field_values where user_id = %s and field_key = %s for update",
        (user_id, field_key),
    )
    row = tx.fetch_one_dict(
        f"""
        insert into profile.field_values
            (user_id, field_key, value, source, extraction, verified,
             evidence_ref, expires_at)
        values (%s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
        on conflict (user_id, field_key) do update
           set value = excluded.value,
               source = excluded.source,
               extraction = excluded.extraction,
               verified = excluded.verified,
               evidence_ref = excluded.evidence_ref,
               expires_at = excluded.expires_at
        returning {', '.join(_VALUE_COLUMNS)}
        """,
        (user_id, field_key, _json(value), source, extraction, verified,
         _json(evidence_ref), expires_at),
    )
    _insert_event(tx, user_id, field_key, "set", old[0] if old else None, value, source, actor)
    return row


def _delete_in_tx(tx, user_id, field_key, actor) -> bool:
    row = tx.fetch_one(
        "delete from profile.field_values where user_id = %s and field_key = %s returning value, source",
        (user_id, field_key),
    )
    if row is None:
        return False
    _insert_event(tx, user_id, field_key, "delete", row[0], None, row[1], actor)
    return True


def _check_source(source: str, extraction: str | None = None) -> None:
    if source not in SOURCES:
        raise ValueError(f"unknown source: {source}")
    if extraction is not None and extraction not in EXTRACTIONS:
        raise ValueError(f"unknown extraction: {extraction}")


def set_field(
    user_id: str,
    field_key: str,
    value,
    *,
    source: str,
    actor: str,
    extraction: str | None = None,
    evidence_ref: dict | None = None,
    verified: bool = False,
    expires_at=None,
) -> dict:
    """Creates or overwrites one field value. `actor` identifies who made
    the change, e.g. 'user:<id>', 'agent:resume', 'system:<job>'.
    extraction/evidence_ref are only allowed for source='CV' (a table
    CHECK); the value itself is validated by the field_values trigger.
    Returns the stored row."""
    _check_source(source, extraction)
    with profile_db.transaction() as tx:
        return _upsert_in_tx(tx, user_id, field_key, value, source, actor,
                             extraction, evidence_ref, verified, expires_at)


def set_fields(
    user_id: str, changes: dict, *, source: str, actor: str, from_cv: dict[str, dict] | None = None
) -> None:
    """Applies several field changes atomically: a value upserts the field,
    None deletes it (a no-op if it wasn't stored). Keys in `from_cv`
    ({field_key: evidence_ref}) are stored as source CV instead — a literal
    extraction the user has checked, so verified."""
    _check_source(source)
    from_cv = from_cv or {}
    with profile_db.transaction() as tx:
        for field_key, value in changes.items():
            if value is None:
                _delete_in_tx(tx, user_id, field_key, actor)
            elif field_key in from_cv:
                _upsert_in_tx(tx, user_id, field_key, value, "CV", actor,
                              extraction="literal", evidence_ref=from_cv[field_key], verified=True)
            else:
                _upsert_in_tx(tx, user_id, field_key, value, source, actor)


def confirm_field(user_id: str, field_key: str, *, actor: str) -> bool:
    """The user confirmed the stored value: mark it verified.
    Returns False if there is no stored value."""
    with profile_db.transaction() as tx:
        row = tx.fetch_one(
            """
            update profile.field_values
               set verified = true
             where user_id = %s and field_key = %s
            returning value, source
            """,
            (user_id, field_key),
        )
        if row is None:
            return False
        _insert_event(tx, user_id, field_key, "confirm", row[0], row[0], row[1], actor)
    return True


def delete_field(user_id: str, field_key: str, *, actor: str) -> bool:
    """Returns False if there was no stored value."""
    with profile_db.transaction() as tx:
        return _delete_in_tx(tx, user_id, field_key, actor)


# conflicts

def record_conflict(
    user_id: str,
    field_key: str,
    *,
    kind: str,
    current_value,
    current_source: str | None,
    candidate_value,
    candidate_source: str,
) -> int:
    if kind not in CONFLICT_KINDS:
        raise ValueError(f"unknown conflict kind: {kind}")
    row = profile_db.execute_returning(
        """
        insert into profile.field_conflicts
            (user_id, field_key, kind, current_value, current_source,
             candidate_value, candidate_source)
        values (%s, %s, %s, %s::jsonb, %s, %s::jsonb, %s)
        returning id
        """,
        (user_id, field_key, kind, _json(current_value), current_source,
         _json(candidate_value), candidate_source),
    )
    return row[0]


def list_open_conflicts(user_id: str) -> list[dict]:
    return profile_db.fetch_all_dict(
        """
        select id, field_key, kind, current_value, current_source,
               candidate_value, candidate_source, created_at
          from profile.field_conflicts
         where user_id = %s and status = 'open'
         order by created_at
        """,
        (user_id,),
    )


def close_conflict(conflict_id: int, status: str) -> bool:
    """Marks an open conflict resolved or dismissed. Returns False if it
    doesn't exist or is already closed. Applying the winning value is the
    caller's job (via set_field)."""
    if status not in CONFLICT_RESOLUTIONS:
        raise ValueError(f"unknown conflict resolution: {status}")
    row = profile_db.execute_returning(
        """
        update profile.field_conflicts
           set status = %s, resolved_at = now()
         where id = %s and status = 'open'
        returning id
        """,
        (status, conflict_id),
    )
    return row is not None


# consents

def get_current_consents(user_id: str) -> dict[str, dict]:
    """consent_key -> {granted, options, notice_version, created_at}, the
    latest decision per key. A key never answered is absent (= not
    granted)."""
    rows = profile_db.fetch_all_dict(
        """
        select consent_key, granted, options, notice_version, created_at
          from profile.v_consents_current
         where user_id = %s
        """,
        (user_id,),
    )
    return {r.pop("consent_key"): r for r in rows}


def has_consent(user_id: str, consent_key: str) -> bool:
    row = profile_db.fetch_one("select profile.has_consent(%s, %s)", (user_id, consent_key))
    return bool(row and row[0])


def purpose_consent_key(purpose: str) -> str | None:
    """The consent a purpose's facts need (profile.purpose_consents), or
    None when the purpose needs none."""
    row = profile_db.fetch_one("select consent_key from profile.purpose_consents where purpose = %s", (purpose,))
    return row[0] if row else None


def record_consent(
    user_id: str, consent_key: str, granted: bool, *, notice_version: str, options: dict | None = None
) -> None:
    """Appends a decision; the history is never rewritten."""
    profile_db.execute(
        """
        insert into profile.consent_events (user_id, consent_key, granted, options, notice_version)
        values (%s, %s, %s, %s::jsonb, %s)
        """,
        (user_id, consent_key, granted, json.dumps(options or {}), notice_version),
    )


# derived labels

def get_derived(user_id: str) -> dict | None:
    return profile_db.fetch_one_dict(
        f"select {', '.join(_DERIVED_COLUMNS)}, rules_version, computed_at from profile.derived where user_id = %s",
        (user_id,),
    )


def save_derived(user_id: str, values: dict, *, rules_version: str) -> None:
    """Full overwrite: derived labels are always recomputed together, so a
    label missing from `values` is stored as NULL (graduation_risk_flags as
    [])."""
    cols = list(_DERIVED_COLUMNS)
    params = []
    for c in cols:
        v = values.get(c)
        if c == "graduation_risk_flags" and v is None:
            v = []
        params.append(_json(v) if c in _DERIVED_JSON_COLUMNS else v)
    placeholders = ", ".join("%s::jsonb" if c in _DERIVED_JSON_COLUMNS else "%s" for c in cols)
    profile_db.execute(
        f"""
        insert into profile.derived (user_id, {', '.join(cols)}, rules_version, computed_at)
        values (%s, {placeholders}, %s, now())
        on conflict (user_id) do update
           set {', '.join(f'{c} = excluded.{c}' for c in cols)},
               rules_version = excluded.rules_version,
               computed_at = now()
        """,
        [user_id, *params, rules_version],
    )


# CV documents

_CV_COLUMNS = (
    "id", "storage_bucket", "storage_path", "retain_original", "parse_status", "uploaded_at", "purged_at",
    "candidates", "error", "parsed_at",
)


def create_cv_document(
    user_id: str, *, storage_bucket: str | None, storage_path: str | None, retain_original: bool = False
) -> dict:
    return profile_db.fetch_one_dict(
        f"""
        insert into profile.cv_documents (user_id, storage_bucket, storage_path, retain_original)
        values (%s, %s, %s, %s)
        returning {', '.join(_CV_COLUMNS)}
        """,
        (user_id, storage_bucket, storage_path, retain_original),
    )


def get_latest_cv_document(user_id: str) -> dict | None:
    return profile_db.fetch_one_dict(
        f"""
        select {', '.join(_CV_COLUMNS)} from profile.cv_documents
         where user_id = %s order by uploaded_at desc limit 1
        """,
        (user_id,),
    )


def get_cv_document(user_id: str, document_id: str) -> dict | None:
    """One of this user's CV documents; None if it isn't theirs."""
    return profile_db.fetch_one_dict(
        f"select {', '.join(_CV_COLUMNS)} from profile.cv_documents where id = %s and user_id = %s",
        (document_id, user_id),
    )


def save_cv_result(document_id: str, *, candidates: dict | None = None, error: str | None = None) -> bool:
    """Finishes a parse: the extracted candidates ({field_key: {value,
    quote}}) mark it parsed, an error marks it failed."""
    status = "failed" if error else "parsed"
    row = profile_db.execute_returning(
        """
        update profile.cv_documents
           set parse_status = %s, candidates = %s::jsonb, error = %s, parsed_at = now()
         where id = %s
        returning id
        """,
        (status, _json(candidates or {}), error, document_id),
    )
    return row is not None


def set_cv_parse_status(document_id: str, status: str) -> bool:
    if status not in CV_PARSE_STATUSES:
        raise ValueError(f"unknown parse status: {status}")
    row = profile_db.execute_returning(
        "update profile.cv_documents set parse_status = %s where id = %s returning id",
        (status, document_id),
    )
    return row is not None


def mark_cv_purged(document_id: str) -> bool:
    """Records that the original file was deleted from storage; the row
    stays as the audit trail."""
    row = profile_db.execute_returning(
        """
        update profile.cv_documents
           set purged_at = now(), storage_path = null
         where id = %s and purged_at is null
        returning id
        """,
        (document_id,),
    )
    return row is not None


def list_cv_quotes(user_id: str) -> dict[str, str]:
    """field_key -> the CV quote behind each value stored from a CV."""
    rows = profile_db.fetch_all(
        """
        select field_key, evidence_ref->>'quote' from profile.field_values
         where user_id = %s and source = 'CV' and evidence_ref ? 'quote'
        """,
        (user_id,),
    )
    return {key: quote for key, quote in rows}


def delete_cv_data(user_id: str) -> int:
    """Forgets everything kept from the user's CVs: every import's
    candidates (the row stays, marked purged, as the upload's audit trail),
    the quotes behind values stored from a CV (the values themselves stay),
    and open conflicts raised by a CV. Returns how many imports were
    cleared."""
    with profile_db.transaction() as tx:
        cleared = tx.fetch_all(
            """
            update profile.cv_documents
               set candidates = '{}'::jsonb, purged_at = coalesce(purged_at, now()), storage_path = null
             where user_id = %s and (candidates <> '{}'::jsonb or purged_at is null)
            returning id
            """,
            (user_id,),
        )
        tx.execute(
            "update profile.field_values set evidence_ref = null where user_id = %s and source = 'CV'",
            (user_id,),
        )
        tx.execute(
            """
            update profile.field_conflicts set status = 'dismissed', resolved_at = now()
             where user_id = %s and kind = 'self_vs_cv' and status = 'open'
            """,
            (user_id,),
        )
    return len(cleared)


def list_user_ids() -> list[str]:
    """Every user with a profile (one per account)."""
    return [str(row[0]) for row in profile_db.fetch_all("select user_id from profile.profiles order by user_id")]
