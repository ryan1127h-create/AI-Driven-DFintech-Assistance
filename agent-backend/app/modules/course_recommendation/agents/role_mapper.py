"""
Free-text role → skill tags, via the LLM.

The 6 standard roles (career_roles table) come with curated skill lists and
never pass through here. For anything else the user types ("quant
researcher", "web3 founder", ...), the LLM reasons about what that job
needs — but may only answer with tags from our fixed 9-skill vocabulary,
so everything downstream (gap computation, course matching) stays grounded
in data we actually have. Returns None on any failure; the caller then
proceeds without role-based matching and says so in `notes`.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.kimi_client import build_chat_llm

# The complete skill vocabulary (course chunks + career_roles both use it).
ALL_SKILL_IDS = (
    "ai_ml", "data_analytics", "finance", "payments_systems", "product",
    "programming", "regulation", "risk_modeling", "security",
)

_MAX_TOKENS = 1500

_SYSTEM_PROMPT = """\
You map a career goal to skill tags for a FinTech master's programme
course recommender.

Given the user's target role, pick the 3 to 5 most relevant tags from this
fixed vocabulary (use these exact ids, never invent new ones):
- ai_ml: machine learning / AI
- data_analytics: data analysis and analytics
- finance: finance and financial markets knowledge
- payments_systems: payments, blockchain, trading systems
- product: product and business understanding
- programming: software development
- regulation: compliance and regulation
- risk_modeling: quantitative risk modelling
- security: cyber security and resilience

Reply with ONLY a valid JSON object, no markdown:
{"skills": ["finance", "risk_modeling", "programming"]}
If the input is not a recognisable job or career goal, reply {"skills": []}.
"""


def map_role_to_skills(free_text_role: str) -> list[str] | None:
    """Returns 3-5 skill ids for a free-text role, or None if the LLM is
    unavailable or gives nothing usable."""
    try:
        response = build_chat_llm(temperature=0, max_tokens=_MAX_TOKENS).invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=free_text_role.strip()),
        ])
        content = response.content if isinstance(response.content, str) else str(response.content)
        raw = json.loads(content.strip()).get("skills", [])
        # Keep only known tags, dedup, cap at 5.
        skills = list(dict.fromkeys(s for s in raw if s in ALL_SKILL_IDS))[:5]
        return skills or None
    except Exception as exc:
        print(f"[course_recommendation.role_mapper] Warning: role mapping failed — {exc}")
        return None
