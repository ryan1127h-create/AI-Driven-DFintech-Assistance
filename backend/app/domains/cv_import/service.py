"""
CV import service: consent and upload checks, text extraction, one
extraction call, then a check of every candidate before it is stored —
its quote must appear in the CV (so nothing invented gets through) and its
value must be one the profile field accepts.
"""

from __future__ import annotations

import json
import re
import time

from app.adapters.redis_cache_adapter import cache
from app.core.errors import ForbiddenError, RateLimitError, ServiceUnavailableError, ValidationError
from app.core.logging import get_logger
from app.core.resilience import run_with_timeout
from app.domains.cv_import import cv_text
from app.domains.profile import interface as profile_interface
from app.domains.specialist.cv_extraction.interface import extract_fields

logger = get_logger(__name__)

CONSENT_KEY = "consent_cv_processing"
MAX_FILE_BYTES = 5 * 1024 * 1024
# Less text than this is a scanned or image-only file, not a readable CV.
MIN_TEXT_CHARS = 200
MAX_QUOTE_CHARS = 300
UPLOADS_PER_HOUR = 3
_EXTRACTION_TIMEOUT_SECONDS = 90.0
_RATE_PREFIX = "cv_import:uploads:"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def check_candidates(raw: dict, targets: list[dict], text: str) -> dict:
    """{field_key: {value, quote}} for the extracted fields that are among
    the targets, quote something the CV really says, and hold a value the
    field accepts (normalized as the profile stores it)."""
    allowed = {t["field_key"] for t in targets}
    haystack = _normalize(text)
    candidates = {}
    for key, item in raw.items():
        if key not in allowed or not isinstance(item, dict):
            continue
        quote = item.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            continue
        quote = quote.strip().strip('"“”').strip()
        if _normalize(quote) not in haystack:
            logger.info("cv candidate %s dropped: quote not found in the CV", key)
            continue
        value = profile_interface.check_value(key, item.get("value"))
        if value is None or value in ([], {}):
            logger.info("cv candidate %s dropped: value not accepted", key)
            continue
        candidates[key] = {"value": value, "quote": quote[:MAX_QUOTE_CHARS]}
    return candidates


def _check_rate(user_id: str) -> None:
    """At most UPLOADS_PER_HOUR extractions per user per hour. Fails open
    when the cache is down: a Redis outage shouldn't block CV import."""
    key = _RATE_PREFIX + user_id
    now = time.time()
    try:
        recent = [t for t in json.loads(cache.get(key) or "[]") if now - t < 3600]
        if len(recent) >= UPLOADS_PER_HOUR:
            minutes = int((3600 - (now - min(recent))) // 60) + 1
            raise RateLimitError(f"You've uploaded {UPLOADS_PER_HOUR} CVs this hour. Try again in {minutes} minutes.")
        cache.set(key, json.dumps([*recent, now]), ttl_seconds=3600)
    except RateLimitError:
        raise
    except Exception as exc:
        logger.warning("cv import rate limit unavailable, allowing upload: %s", exc)


def import_cv(user_id: str, filename: str, data: bytes) -> dict:
    if not profile_interface.has_consent(user_id, CONSENT_KEY):
        raise ForbiddenError("Allow CV processing first.")
    if not data:
        raise ValidationError("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise ValidationError("Your CV must be 5 MB or smaller.")
    text = cv_text.extract_text(data, filename)
    if len(text.strip()) < MIN_TEXT_CHARS:
        raise ValidationError(
            "No text could be read from this file. If it's a scanned CV, upload a text-based PDF or a DOCX instead."
        )
    _check_rate(user_id)

    document_id = profile_interface.start_cv_document(user_id)
    targets = profile_interface.cv_targets(user_id)
    try:
        raw = run_with_timeout(lambda: extract_fields(text, targets), _EXTRACTION_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("cv extraction failed for %s (document %s): %r", user_id, document_id, exc)
        profile_interface.fail_cv_document(document_id, "extraction failed")
        raise ServiceUnavailableError(
            "Your CV couldn't be read right now. Try again, or answer the questions instead."
        ) from exc
    return profile_interface.finish_cv_document(user_id, document_id, check_candidates(raw, targets, text))


def latest_import(user_id: str) -> dict | None:
    return profile_interface.latest_cv_import(user_id)


def delete_cv_data(user_id: str) -> dict:
    return {"cleared_imports": profile_interface.delete_cv_data(user_id)}
