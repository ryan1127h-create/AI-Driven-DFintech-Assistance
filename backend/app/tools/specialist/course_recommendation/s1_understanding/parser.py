"""
S1 — reads a course-recommendation message into a ParsedRequest with one
small model call (JSON out), run alongside S2's data gathering.

The mode comes from the intent classifier (TurnState.course_mode_hint),
which already decided it in the same call that routed the turn here; this
step only extracts what the message asks for. Any failure — the model
unavailable, unparseable output — yields the default request (no
constraints) marked parse_failed, so the recommendation still runs and
the reply says the filters weren't understood.
"""

from __future__ import annotations

import json

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.tools.specialist.course_recommendation.s1_understanding.schema import (
    CAPSTONE_INTENTS,
    SKILLS,
    STUDY_MODES,
    TRACKS,
    WEEKDAYS,
    Mode,
    ParsedRequest,
)

logger = get_logger(__name__)

_MAX_TOKENS = 400

_PROMPT = f"""\
You read one message from a student of the NUS MSc Digital Financial \
Technology asking for course recommendations, and extract what it asks \
for. Extract only what the message actually says — never guess, and use \
an empty list or null for anything it doesn't mention.

Reply with ONLY a JSON object with these keys:
- "include_codes": course codes the student wants to take (e.g. "FT5005").
- "exclude_codes": course codes the student does not want, or has said \
they won't take.
- "preferred_skills": skills they want to build, only from: {", ".join(SKILLS)}.
- "keywords": short English topic words or phrases they're interested in \
that the skills above don't capture (e.g. "deep learning", "trading", \
"python"); translate them to English.
- "vertical_preference": elective tracks they say they're interested in, \
only from: {", ".join(TRACKS)}.
- "workload_style": "less_project" if they want little independent project \
work, "lecture" if they prefer lecture- or discussion-based courses, else null.
- "study_mode": {" or ".join(STUDY_MODES)} if they say how they study, else null.
- "capstone_intent": {", ".join(CAPSTONE_INTENTS)} if they say whether they'll \
do the Capstone (research or internship) or take electives instead, else null.
- "target_semester": "next" if they ask about the next semester or term \
(e.g. "下学期", "next sem"), "S1" or "S2" if they name Semester 1 or 2, else null.
- "unit_cap": the number of units (MCs, 学分) they want to take that \
semester, as an integer, else null.
- "avoid_time_windows": a LIST of time ranges they want to avoid, each \
{{"start": "HH:MM", "end": "HH:MM"}} in 24-hour time — "no evening classes" \
is [{{"start": "18:00", "end": "23:00"}}], "no morning classes" \
[{{"start": "08:00", "end": "12:00"}}].
- "avoid_days": weekdays they want to keep free, from: {", ".join(WEEKDAYS)}.
"""


def parse(message: str, mode: Mode | None) -> ParsedRequest:
    default_mode = mode or "degree_overview"
    if not message.strip():
        return ParsedRequest(mode=default_mode)
    try:
        raw = json.loads(llm.complete(_PROMPT, message, temperature=0, max_tokens=_MAX_TOKENS).strip())
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        return ParsedRequest.model_validate({**raw, "mode": default_mode})
    except Exception:
        logger.exception("course recommendation: parsing the request failed, using no filters")
        return ParsedRequest(mode=default_mode, parse_failed=True)
