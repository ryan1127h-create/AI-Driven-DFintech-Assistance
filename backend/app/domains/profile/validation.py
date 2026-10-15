"""
Field-level rules for the profile, derived from profile.field_definitions
— pure functions, no I/O.

  - which fields a user sees at all, and which of those they may edit
    (editability): storage/layer/sources in the dictionary plus a few rules
    of this app (lifecycle_stage only moves through registration and
    application binding; school-record values are read-only);
  - value validation and normalization for user writes (validate_value),
    mirroring the field_values trigger so a bad value is a 400 with a
    clear message rather than a database error — plus length caps on free
    text, since profile values are re-injected into the user's own chat
    prompt;
  - expiry of admission test scores (drop_expired_items).
"""

from __future__ import annotations

import re
from datetime import date

MAX_TEXT = 300
MAX_LIST_ITEMS = 30
MAX_ITEM_ATTRS = 5

_TERM_RE = re.compile(r"^AY\d{4}/\d{2} (Sem[1-4]|Special Term [12])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Extra attributes a multi-select item may carry next to its `key` (see
# each field's value_spec), and what each attribute accepts.
_ITEM_ATTRS: dict[str, dict] = {
    "languages": {"level": ("fluent", "basic")},
    "certifications": {"level": str},
    "concerns": {"note": str},
    "function_experience": {"internship": bool},
}


class FieldValueError(ValueError):
    def __init__(self, field_key: str, message: str) -> None:
        super().__init__(f"{field_key}: {message}")
        self.field_key = field_key


# --- visibility and editability ---------------------------------------------

def is_displayed(definition: dict) -> bool:
    """Profile fields the user sees: visible, and neither a derived label,
    an account setting nor a consent (those have their own sections, or
    none — derived labels stay internal)."""
    return definition["user_visible"] and definition["storage"] in ("value", "sis")


def lock_reason(definition: dict, entry: dict | None) -> str | None:
    """None if the user may edit this field right now, else why not.
    `entry` is the field's current merged value (v_profile), if any."""
    if not is_displayed(definition):
        return "not a user-editable profile field"
    if definition["storage"] == "sis":
        return "from school records"
    if definition["field_key"] == "lifecycle_stage":
        return "changes through registration and application binding"
    if definition["layer"] == "inferred":
        return "maintained by the system"
    if entry is not None and entry.get("source") == "DB":
        return "from school records"
    return None


# --- values -----------------------------------------------------------------

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(field_key: str, value, max_len: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FieldValueError(field_key, "expects non-empty text")
    value = value.strip()
    if len(value) > max_len:
        raise FieldValueError(field_key, f"text is longer than {max_len} characters")
    return value


# values_ref values: the tables a field may take its options from.
ROLE_TAGS_REF = "knowledge.tags_definition"
PROGRAMS_REF = "program.programs"


def _choice(field_key: str, value, allowed: list | None, ref_keys: set[str] | None):
    """One enum value. Numeric enums (e.g. code_level 0-4) also accept the
    digit string a form select produces."""
    if allowed is not None:
        if isinstance(value, str) and value.lstrip("-").isdigit() and any(_is_number(a) for a in allowed):
            value = int(value)
        if value not in allowed or isinstance(value, bool):
            raise FieldValueError(field_key, f"{value!r} is not an allowed value")
        return value
    if ref_keys is not None:
        if value not in ref_keys:
            raise FieldValueError(field_key, f"{value!r} is not one of the field's options")
        return value
    return _text(field_key, value, 120)


def _multi(field_key: str, value, definition: dict, ref_keys: set[str] | None) -> list:
    if not isinstance(value, list):
        raise FieldValueError(field_key, "expects a list")
    limit = definition["max_items"] or MAX_LIST_ITEMS
    if len(value) > limit:
        raise FieldValueError(field_key, f"allows at most {limit} items")
    allowed = definition["allowed_values"]
    attrs = _ITEM_ATTRS.get(field_key, {})
    out, seen = [], set()
    for item in value:
        if isinstance(item, dict):
            if "key" not in item:
                raise FieldValueError(field_key, "each item needs a key")
            unknown = set(item) - {"key"} - set(attrs)
            if unknown or len(item) > MAX_ITEM_ATTRS:
                raise FieldValueError(field_key, f"unexpected item attributes: {sorted(unknown)}")
            key = _choice(field_key, item["key"], allowed, ref_keys)
            normalized = {"key": key}
            for attr, rule in attrs.items():
                if attr not in item or item[attr] is None:
                    continue
                v = item[attr]
                if rule is bool:
                    if not isinstance(v, bool):
                        raise FieldValueError(field_key, f"{attr} expects true/false")
                elif rule is str:
                    v = _text(field_key, v)
                elif v not in rule:
                    raise FieldValueError(field_key, f"{attr} must be one of {list(rule)}")
                normalized[attr] = v
        else:
            key = _choice(field_key, item, allowed, ref_keys)
            normalized = key
        if key in seen:
            raise FieldValueError(field_key, f"{key!r} is listed twice")
        seen.add(key)
        out.append(normalized)
    return out


def _admission_tests(field_key: str, value, definition: dict) -> list:
    if not isinstance(value, list) or len(value) > 10:
        raise FieldValueError(field_key, "expects a list of at most 10 tests")
    out = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"key", "score", "test_date"}:
            raise FieldValueError(field_key, "each test is {key, score, test_date}")
        test = _choice(field_key, item.get("key"), definition["allowed_values"], None)
        score = item.get("score")
        if isinstance(score, str):
            try:
                score = float(score)
            except ValueError:
                raise FieldValueError(field_key, f"{test} score must be a number") from None
        if not _is_number(score) or score < 0:
            raise FieldValueError(field_key, f"{test} score must be a non-negative number")
        entry = {"key": test, "score": int(score) if float(score).is_integer() else score}
        test_date = item.get("test_date")
        if test_date:
            if not isinstance(test_date, str) or not _DATE_RE.match(test_date):
                raise FieldValueError(field_key, f"{test} test_date must be YYYY-MM-DD")
            try:
                date.fromisoformat(test_date)
            except ValueError:
                raise FieldValueError(field_key, f"{test} test_date is not a real date") from None
            entry["test_date"] = test_date
        out.append(entry)
    return out


def _structured(field_key: str, value, definitions: dict, role_tags: set[str]):
    """`role_tags`: the role tag keys current_position and
    currently_hiring choose role families from."""
    if field_key == "admission_tests":
        return _admission_tests(field_key, value, definitions[field_key])
    if not isinstance(value, dict):
        raise FieldValueError(field_key, "expects an object")
    if field_key == "current_position":
        rules = {
            "role_family": lambda v: _choice(field_key, v, None, role_tags),
            "region": lambda v: _choice(field_key, v, definitions["target_markets"]["allowed_values"], None),
            "seniority": lambda v: _choice(field_key, v, definitions["seniority_level"]["allowed_values"], None),
        }
    elif field_key == "currently_hiring":
        def _hiring(v):
            if not isinstance(v, bool):
                raise FieldValueError(field_key, "hiring expects true/false")
            return v
        rules = {
            "hiring": _hiring,
            "role_families": lambda v: _multi(
                field_key, v, {"max_items": None, "allowed_values": None}, role_tags),
        }
    else:
        raise FieldValueError(field_key, "is not writable")
    unknown = set(value) - set(rules)
    if unknown:
        raise FieldValueError(field_key, f"unexpected attributes: {sorted(unknown)}")
    out = {k: rules[k](v) for k, v in value.items() if v is not None}
    if not out:
        raise FieldValueError(field_key, "needs at least one attribute")
    return out


def validate_value(field_key: str, value, definitions: dict, ref_options: dict[str, set[str]]):
    """Returns the normalized value, or raises FieldValueError. `value` is
    never None here — None means "delete" and is handled by the caller.
    `ref_options`: values_ref -> the keys a field with that values_ref
    accepts (a table missing here accepts nothing)."""
    definition = definitions.get(field_key)
    if definition is None:
        raise FieldValueError(field_key, "unknown field")
    ref = definition["values_ref"]
    ref_keys = set(ref_options.get(ref, ())) if ref else None
    vt = definition["value_type"]
    if vt == "bool":
        if not isinstance(value, bool):
            raise FieldValueError(field_key, "expects true/false")
        return value
    if vt == "year":
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if not isinstance(value, int) or isinstance(value, bool) or not 1950 <= value <= 2100:
            raise FieldValueError(field_key, "expects a year between 1950 and 2100")
        return value
    if vt == "number":
        if not _is_number(value):
            raise FieldValueError(field_key, "expects a number")
        return value
    if vt == "term":
        value = _text(field_key, value, 40)
        if not _TERM_RE.match(value):
            raise FieldValueError(field_key, "expects a term like 'AY2027/28 Sem1'")
        return value
    if vt == "single":
        return _choice(field_key, value, definition["allowed_values"], ref_keys)
    if vt == "multi":
        return _multi(field_key, value, definition, ref_keys)
    if vt == "structured":
        return _structured(field_key, value, definitions, set(ref_options.get(ROLE_TAGS_REF, ())))
    raise FieldValueError(field_key, "is not writable")


# --- expiry -----------------------------------------------------------------

def drop_expired_items(value, definition: dict, today: date):
    """admission_tests-style per-item expiry: items whose test_date is older
    than the test's validity (expiry_rule.validity_years) are dropped.
    Anything else is returned unchanged."""
    rule = definition.get("expiry_rule") or {}
    validity = rule.get("validity_years")
    if not validity or rule.get("per_item_by") != "test_date" or not isinstance(value, list):
        return value
    kept = []
    for item in value:
        years = validity.get(item.get("key")) if isinstance(item, dict) else None
        test_date = item.get("test_date") if isinstance(item, dict) else None
        if years and test_date:
            try:
                taken = date.fromisoformat(test_date)
            except ValueError:
                taken = None
            if taken is not None:
                try:
                    expires = taken.replace(year=taken.year + years)
                except ValueError:  # 29 Feb
                    expires = taken.replace(year=taken.year + years, day=28)
                if expires <= today:
                    continue
        kept.append(item)
    return kept
