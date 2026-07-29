"""
Structured user profile store — persists extracted applicant facts
(background, test scores, target role, etc.) in the conversation Supabase
project, one row per user_id. See app/core/user_profile_schema.sql.

Two responsibilities kept separate:
  - UserProfileStore: plain get/merge/write against the `user_profiles` table.
  - extract_profile_fields(): one small Groq call that reads the latest turn
    and returns only the fields it newly learned (a partial diff, not the
    full profile) — kept partial so a bad LLM output can't wipe out
    previously-known fields.

update_profile_after_turn() ties both together and is meant to be run via
FastAPI's BackgroundTasks (see app/api/chat.py) so it never adds latency to
the turn the user is waiting on.
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings

load_dotenv()

# Grounded in the live app.career_roles.role_id values (see plan Phase 5) —
# keeping this in sync with that table means target_role_std can later be
# used for a direct lookup, not just free-text retrieval.
_TARGET_ROLE_VALUES = [
    "compliance_regtech", "data_analytics", "digital_banking",
    "fintech_pm", "payments", "quant_risk",
]

# Grounded in the live app.course_rules.intake values.
_INTAKE_VALUES = ["2025-08-and-earlier", "2026-08-onwards"]

_LIFECYCLE_VALUES = ["prospect", "applicant", "admitted", "student", "alumni"]

_EXTRACTION_PROMPT = f"""\
You extract structured applicant facts from one turn of a conversation with \
an NUS MSc DFinTech admissions assistant.

Return ONLY a JSON object containing fields that are newly mentioned or \
updated in THIS turn (the latest user message and the assistant's reply). \
Omit any field not mentioned this turn — do not guess, do not repeat facts \
already in the existing profile below unless this turn changes them.

Fields (all optional, omit what wasn't mentioned):
- academic_background: {{"raw": "<user's own words>", "std": "<finance|cs_computing|engineering|business|other>"}}
- school_tier: free text describing the applicant's undergrad tier (e.g. "双非", "985", "海外QS100")
- tech_level: {{"raw": "<user's own words>", "std": "<none|basic|intermediate|advanced>"}}
- work_years: integer
- gmat: integer or null if explicitly stated as not taken
- gre: integer or null
- toefl: integer or null
- ielts: number or null
- target_role_raw: "<user's own words about desired career>"
- target_role_std: one of {_TARGET_ROLE_VALUES} — only set this if the role \
clearly matches one of these; otherwise omit it (do not invent a new value)
- target_industry: {{"raw": "<user's own words>", "std": "<short lowercase category>"}}
- lifecycle_stage: one of {_LIFECYCLE_VALUES}
- application_term: free text (e.g. "2026 Fall")
- intake_std: one of {_INTAKE_VALUES} — only if clearly determinable, else omit
- personalization_opt_out: true ONLY if the user explicitly asks not to have \
their information remembered/tracked

Existing known profile (for context — do not repeat these back unless they \
changed this turn):
__EXISTING_PROFILE_JSON__

Respond with ONLY the JSON object, no markdown, no explanation. If nothing \
new was mentioned, respond with {{}}."""


def _build_extraction_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_tokens=400,
    )


def extract_profile_fields(existing_profile: dict, user_message: str, agent_reply: str) -> dict:
    """Returns a partial dict of newly-learned fields, or {} on any failure
    (never raises — this runs in a background task, a failure here should
    never surface as an error anywhere)."""
    try:
        llm = _build_extraction_llm()
        prompt = _EXTRACTION_PROMPT.replace(
            "__EXISTING_PROFILE_JSON__", json.dumps(existing_profile, ensure_ascii=False)
        )
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"User: {user_message}\nAssistant: {agent_reply}"),
        ])
        result = json.loads(response.content.strip())
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        print(f"[user_profile_store] Warning: extraction failed — {exc}")
        return {}


def _deep_merge(base: dict, updates: dict) -> dict:
    """Only overwrites fields updates actually provides (non-null). Nested
    {"raw":..., "std":...} dicts are merged the same way, so e.g. an updated
    "std" alone doesn't wipe out a previously-captured "raw"."""
    merged = dict(base)
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class UserProfileStore:
    """psycopg-backed store for the `user_profiles` table (conversation
    Supabase project — same database as SupabaseSessionStore, but this is
    its own connection since the two are logically independent stores)."""

    def __init__(self):
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(settings.conversation_database_url, connect_timeout=5)
        return self._conn

    def get(self, user_id: str) -> dict:
        with self._connection().cursor() as cur:
            cur.execute("select profile from user_profiles where user_id = %s", (user_id,))
            row = cur.fetchone()
        return row[0] if row and row[0] else {}

    def merge(self, user_id: str, extracted: dict, new_topics: list[str]) -> dict:
        existing = self.get(user_id)
        merged = _deep_merge(existing, extracted)

        if new_topics:
            asked = list(merged.get("asked_topics") or [])
            for topic in new_topics:
                if topic not in asked:
                    asked.append(topic)
            merged["asked_topics"] = asked

        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into user_profiles (user_id, profile, updated_at)
                values (%s, %s::jsonb, now())
                on conflict (user_id) do update
                  set profile = excluded.profile, updated_at = now()
                """,
                (user_id, json.dumps(merged, ensure_ascii=False)),
            )
        conn.commit()
        return merged


_store: UserProfileStore | None = None


def get_user_profile_store() -> UserProfileStore:
    global _store
    if _store is None:
        _store = UserProfileStore()
    return _store


def update_profile_after_turn(user_id: str, user_message: str, agent_reply: str, intents: list[str]) -> None:
    """Background-task entry point: extract + merge + persist. Never raises."""
    try:
        store = get_user_profile_store()
        existing = store.get(user_id)

        if existing.get("personalization_opt_out"):
            return
        if intents == ["general"]:
            return  # nothing to extract from pure chit-chat, save a Groq call

        extracted = extract_profile_fields(existing, user_message, agent_reply)
        store.merge(user_id, extracted, new_topics=intents)
    except Exception as exc:
        print(f"[user_profile_store] Warning: update_profile_after_turn failed — {exc}")


def summarize_profile(profile: dict) -> str:
    """Renders the profile into a compact block of text to prepend to the
    LLM prompt. Empty profile -> empty string (caller should skip injecting
    a SystemMessage entirely in that case)."""
    if not profile:
        return ""

    lines = []

    def _raw_std(field: str, label: str):
        v = profile.get(field)
        if isinstance(v, dict) and (v.get("std") or v.get("raw")):
            lines.append(f"- {label}: {v.get('std') or v.get('raw')}")

    _raw_std("academic_background", "Academic background")
    if profile.get("school_tier"):
        lines.append(f"- Undergrad tier: {profile['school_tier']}")
    _raw_std("tech_level", "Technical level")
    if profile.get("work_years") is not None:
        lines.append(f"- Work experience: {profile['work_years']} years")
    for field, label in [("gmat", "GMAT"), ("gre", "GRE"), ("toefl", "TOEFL"), ("ielts", "IELTS")]:
        if profile.get(field) is not None:
            lines.append(f"- {label}: {profile[field]}")
    if profile.get("target_role_std") or profile.get("target_role_raw"):
        lines.append(f"- Target career: {profile.get('target_role_std') or profile.get('target_role_raw')}")
    _raw_std("target_industry", "Target industry")
    if profile.get("lifecycle_stage"):
        lines.append(f"- Lifecycle stage: {profile['lifecycle_stage']}")
    if profile.get("application_term"):
        lines.append(f"- Application term: {profile['application_term']}")
    if profile.get("asked_topics"):
        lines.append(f"- Already discussed: {', '.join(profile['asked_topics'])}")

    if not lines:
        return ""

    return "Known applicant profile (from earlier in this relationship, use it but don't recite it verbatim):\n" + "\n".join(lines)
