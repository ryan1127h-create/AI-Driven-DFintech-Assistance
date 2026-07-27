"""Extract applicant profile fields from natural language or an uploaded CV.

Two steps:
  parse_file()    .docx / .pdf bytes -> plain text
  extract_fields() free text -> form-field dict via DeepSeek (values constrained
                   to the same enums the form uses; invalid values dropped)

The extracted dict pre-fills the review form; the student confirms/edits before
agents run. DeepSeek is required for this path (raises if no API key).
"""
from __future__ import annotations

import io
import json
import os

from common import config
from common.profile import (
    ApplicationType,
    DegreeLevel,
    FieldOfStudy,
    LifecycleStage,
    Proficiency,
    TargetRole,
)
from .profile_form import COMMON_DOCS

ALLOWED_EXTENSIONS = {".docx", ".pdf"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

# Allowed values per field (single-value unless noted as list).
_ALLOWED = {
    "lifecycle_stage": {"applicant", "current"},
    "degree_level": {e.value for e in DegreeLevel},
    "field_of_study": {e.value for e in FieldOfStudy},
    "technical_proficiency": {e.value for e in Proficiency},
    "finance_knowledge": {e.value for e in Proficiency},
    "application_type": {e.value for e in ApplicationType},
}
_ALLOWED_LIST = {
    "target_roles": {e.value for e in TargetRole},
    "submitted_documents": set(COMMON_DOCS),
}


class ProfileExtractionError(RuntimeError):
    pass


# ---------- file parsing ----------
def parse_file(filename: str, data: bytes) -> str:
    """Extract plain text from an uploaded .docx or .pdf. Raises on bad input."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ProfileExtractionError(f"Unsupported file type: {ext} (only .docx / .pdf are supported)")
    if len(data) > MAX_BYTES:
        raise ProfileExtractionError("File is too large (5MB limit)")

    if ext == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # .pdf
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    return "\n".join(pages).strip()


# ---------- LLM extraction ----------
_SYSTEM = (
    "You extract a graduate-school applicant's profile from free text or a CV. "
    "Return ONLY a JSON object with these keys (omit a key if unknown):\n"
    "lifecycle_stage (applicant|current), degree_level "
    "(high_school|bachelor|master|phd), field_of_study (computer_science|finance|"
    "economics|engineering|mathematics|business|other), work_years (integer), "
    "country (ISO 3166-1 alpha-2, e.g. SG), technical_proficiency/finance_knowledge "
    "(none|basic|intermediate|advanced), target_roles (array of: fintech_pm|"
    "quant_risk|digital_banking|payments|compliance_regtech|data_analytics), "
    "application_type (full_time|part_time), submitted_documents (array of valid "
    "application material keys such as personal_statement|cv|proof_of_residence|"
    "degree_certificate|transcript). Use ONLY the allowed "
    "values. Do not invent facts. Output valid JSON only."
)


def _client():
    if not config.is_configured():
        raise ProfileExtractionError(
            "DeepSeek API key is not configured. Add it on the /settings page, or set environment variable "
            "DEEPSEEK_API_KEY。"
        )
    from openai import OpenAI

    return OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())


def coerce_fields(raw: dict) -> dict:
    """Keep only known fields with allowed values; coerce types. Pure function."""
    out: dict = {}
    for key, allowed in _ALLOWED.items():
        val = raw.get(key)
        if isinstance(val, str) and val in allowed:
            out[key] = val
    for key, allowed in _ALLOWED_LIST.items():
        vals = raw.get(key)
        if isinstance(vals, list):
            kept = [v for v in vals if isinstance(v, str) and v in allowed]
            if kept:
                out[key] = kept
    wy = raw.get("work_years")
    if isinstance(wy, int) and wy >= 0:
        out["work_years"] = wy
    elif isinstance(wy, str) and wy.strip().isdigit():
        out["work_years"] = int(wy.strip())
    country = raw.get("country")
    if isinstance(country, str) and len(country.strip()) == 2:
        out["country"] = country.strip().upper()
    return out



_COUNTRY_HINTS = {
    "singapore": "SG", "sg": "SG", "china": "CN", "mainland china": "CN", "cn": "CN",
    "india": "IN", "in": "IN", "malaysia": "MY", "my": "MY", "indonesia": "ID",
    "vietnam": "VN", "thailand": "TH", "hong kong": "HK", "hk": "HK", "taiwan": "TW",
}


def _contains_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def heuristic_extract_fields(text: str) -> dict:
    """Local fallback extractor used when the LLM key is unavailable.

    It intentionally stays conservative: only high-confidence keyword matches are
    used, and the confirmation page asks the user to review every field.
    """
    raw = text or ""
    t = raw.lower()
    out: dict = {}

    if _contains_any(t, ["phd", "doctor of philosophy"]):
        out["degree_level"] = "phd"
    elif _contains_any(t, ["master", "msc", "m.sc", "mfin", "meng", "m.eng"]):
        out["degree_level"] = "master"
    elif _contains_any(t, ["bachelor", "bsc", "b.sc", "ba ", "b.a", "undergraduate"]):
        out["degree_level"] = "bachelor"
    elif _contains_any(t, ["high school", "secondary school"]):
        out["degree_level"] = "high_school"

    if _contains_any(t, ["computer science", "software", "data science", "information systems", "network engineering", "programming"]):
        out["field_of_study"] = "computer_science"
    elif _contains_any(t, ["financial engineering", "engineering", "electrical", "mechanical", "industrial engineering"]):
        out["field_of_study"] = "engineering"
    elif _contains_any(t, ["finance", "banking", "investment", "securities", "trading"]):
        out["field_of_study"] = "finance"
    elif _contains_any(t, ["economics", "econometrics"]):
        out["field_of_study"] = "economics"
    elif _contains_any(t, ["mathematics", "statistics", "statistical"]):
        out["field_of_study"] = "mathematics"
    elif _contains_any(t, ["business", "management", "marketing"]):
        out["field_of_study"] = "business"

    import re
    m = re.search(r"(\d+)\s*(?:\+\s*)?(?:years?|yrs?|y)\b", t)
    if m:
        out["work_years"] = int(m.group(1))

    for key, code in _COUNTRY_HINTS.items():
        if re.search(rf"\b{re.escape(key)}\b", t):
            out["country"] = code
            break

    if _contains_any(t, ["part-time", "part time", "parttime"]):
        out["application_type"] = "part_time"
    elif _contains_any(t, ["full-time", "full time", "fulltime"]):
        out["application_type"] = "full_time"

    tech_hits = ["python", "java", "c++", "sql", "r ", "matlab", "machine learning", "deep learning", "react", "javascript"]
    if _contains_any(t, ["advanced python", "expert", "senior developer"]):
        out["technical_proficiency"] = "advanced"
    elif _contains_any(t, tech_hits):
        out["technical_proficiency"] = "intermediate"
    elif _contains_any(t, ["basic coding", "basic programming"]):
        out["technical_proficiency"] = "basic"

    if _contains_any(t, ["quant", "risk", "portfolio", "derivative", "trading", "investment", "securities", "bank", "fintech", "financial"]):
        out["finance_knowledge"] = "intermediate"
    elif _contains_any(t, ["basic finance", "introductory finance"]):
        out["finance_knowledge"] = "basic"

    roles = []
    if _contains_any(t, ["product manager", "product management", "fintech pm", "pm role"]):
        roles.append("fintech_pm")
    if _contains_any(t, ["quant", "risk", "risk management", "trading", "financial analyst"]):
        roles.append("quant_risk")
    if _contains_any(t, ["digital banking", "banking", "bank"]):
        roles.append("digital_banking")
    if _contains_any(t, ["payment", "payments", "blockchain", "transaction"]):
        roles.append("payments")
    if _contains_any(t, ["compliance", "regtech", "regulation", "aml", "anti-money laundering"]):
        roles.append("compliance_regtech")
    if _contains_any(t, ["data analyst", "data analytics", "analytics", "machine learning", "data scientist", "ai"]):
        roles.append("data_analytics")
    if roles:
        out["target_roles"] = list(dict.fromkeys(roles))

    codes = sorted(set(re.findall(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b", raw.upper())))
    if codes:
        out["completed_modules"] = ", ".join(codes)

    out["_extraction_method"] = "local_fallback"
    return coerce_fields(out) | {k: v for k, v in out.items() if k.startswith("_") or k == "completed_modules"}


def extract_fields(text: str) -> dict:
    """Free text -> validated form-field dict.

    DeepSeek is used when configured. Otherwise the UI still shows a useful
    prefilled review form using the conservative local fallback above, instead
    of leaving Step 2 looking unchanged.
    """
    if not text or not text.strip():
        return {}
    fallback = heuristic_extract_fields(text)
    if not config.is_configured():
        fallback["_notice"] = (
            "AI CV extraction is not configured, so Step 2 was prefilled using local keyword matching. "
            "Please review and correct the fields before generating the analysis."
        )
        return fallback
    try:
        model = config.get_model()
        client = _client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text[:8000]},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        if not content:
            raise ProfileExtractionError("DeepSeek returned empty content")
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ProfileExtractionError("DeepSeek returned a non-object JSON value")
        llm_out = coerce_fields(raw)
        if llm_out:
            llm_out["_extraction_method"] = "deepseek"
            return llm_out
        fallback["_notice"] = "The AI extractor returned no confident fields, so local keyword matching was used. Please review the profile."
        return fallback
    except Exception as e:
        fallback["_notice"] = f"AI extraction was unavailable ({e}); local keyword matching was used. Please review the profile."
        return fallback
