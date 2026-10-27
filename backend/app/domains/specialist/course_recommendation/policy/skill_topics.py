"""
Which role tags make a course *about* a skill.

A course's skills are derived from its role tags (the union of each tag's
required skills), so a course tagged only for Machine Learning & AI or
Cybersecurity still carries "finance" — those roles list finance among
their skills. That says a course is useful for such a role, not that it
teaches finance. When a student asks to build a skill, a course counts as
building it when it carries one of the skill's own topic tags below.

Keys are the knowledge base's role-skill vocabulary
(knowledge.tags_definition.required_skills); values are role tags
(knowledge.tags_definition.tag).
"""

from __future__ import annotations

SKILL_TOPIC_TAGS: dict[str, frozenset[str]] = {
    "finance": frozenset({"finance_investment", "quantitative_finance"}),
    "risk_modeling": frozenset({"risk_management", "quantitative_finance"}),
    "ai_ml": frozenset({"machine_learning_ai"}),
    "data_analytics": frozenset({"data_analytics"}),
    "data_engineering": frozenset({"data_engineering"}),
    "programming": frozenset({"software_engineering"}),
    "security": frozenset({"cybersecurity"}),
    "regulation": frozenset({"regulation_governance"}),
    "payments_systems": frozenset({"blockchain"}),
    "product": frozenset({"product_business", "entrepreneurship"}),
}
