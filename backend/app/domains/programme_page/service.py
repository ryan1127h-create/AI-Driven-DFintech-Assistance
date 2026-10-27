"""
The public programme page (frontend /programme): what MSc DFT is, what it
teaches, who can apply, what it costs, where graduates go and alumni
stories — for visitors who aren't signed in and for prospective and
applying students.

Everything is read from the curated sources the assistant answers from
(program_catalog, knowledge_retrieval, alumni), never written here, so a
staff edit in the knowledge base shows on the page without a deploy. Each
section carries its official source pages and the date the facts were
verified; the curriculum's structure follows the same rules the course
planner applies (course_recommendation.requirement_role).

Alumni stories come only from alumni who chose to share with prospective
students; a visitor who isn't signed in sees the story without the name.
"""

from __future__ import annotations

import time
from datetime import date

from app.domains.alumni import interface as alumni
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.program_catalog import interface as program_catalog
from app.domains.specialist.course_recommendation import interface as course_recommendation

# The page is the same for everyone (but for alumni names), so it is built
# at most this often.
_CACHE_SECONDS = 300
_cache: dict = {"at": 0.0, "page": None}

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_MODES = {"full_time": "Full-time", "part_time": "Part-time"}
# Curriculum skill areas (program.curriculum_areas, knowledge role tags' required_skills).
_SKILLS = {
    "ai_ml": "Machine learning & AI", "data_analytics": "Data analytics", "data_engineering": "Data engineering",
    "finance": "Finance", "payments_systems": "Payments & blockchain systems", "product": "Product & business",
    "programming": "Programming", "regulation": "Regulation & compliance", "risk_modeling": "Risk modelling",
    "security": "Security",
}
_COVERAGE = {"required": "Required core", "core_option": "Core option", "elective": "Elective"}
_FUNDING_FOR = {"sg_citizen": "Singapore citizens", "sg_pr": "Singapore PRs", "alumni": "NUS alumni",
                "international": "international students"}
_WORK_EXPERIENCE = {"not_required": "Not required", "preferred": "Preferred", "required": "Required"}
_GMAT_GRE = {"required": "Required", "recommended": "Recommended", "optional": "Optional", "not_required": "Not required"}
_DESCRIPTION_CHARS = 280


def _money(amount, currency: str | None) -> str | None:
    if amount is None:
        return None
    prefix = "S$" if currency == "SGD" else f"{currency} " if currency else ""
    return f"{prefix}{float(amount):,.0f}"


def _day(value: date | None) -> str | None:
    return f"{value.day} {_MONTHS[value.month - 1][:3]} {value.year}" if value else None


def _short(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    if len(text) <= _DESCRIPTION_CHARS:
        return text or None
    return text[:_DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"


def _sources(program: dict, *fields: str) -> list[str]:
    urls = [s["source_url"] for f in fields for s in program["sources"].get(f, []) if s.get("role") == "primary"]
    return list(dict.fromkeys(u for u in urls if u))


def _overview(program: dict) -> dict:
    facts = program["facts"]
    modes = [_MODES.get(m, m) for m in facts.get("study_modes") or []]
    durations = [f"{int(facts[k])} months {label.lower()}"
                 for k, label in (("duration_ft_months", "full-time"), ("duration_pt_months", "part-time"))
                 if facts.get(k)]
    window = next(iter(program["deadlines"]), None)
    tuition = next(iter(program["fees"]), None)
    key_facts = [
        {"label": "Duration", "value": " · ".join(durations) or None},
        {"label": "Units to graduate", "value": f"{int(facts['total_credits'])} {facts.get('credit_unit') or 'Units'}"
         if facts.get("total_credits") else None},
        {"label": "Intake", "value": ", ".join(_MONTHS[m - 1] for m in facts.get("intake_months") or []) or None},
        {"label": "Study modes", "value": " or ".join(modes) or None},
        {"label": "Applications", "value": f"{_day(window['opens_on'])} – {_day(window['closes_on'])}" if window else None},
        {"label": "Tuition", "value": (_money(tuition["amount"], tuition["currency"])
                                       + (" incl. GST" if tuition.get("includes_tax") else "")) if tuition else None},
    ]
    return {
        "name": program["name"], "short_name": program["short_name"], "summary": program["summary"],
        "official_url": program["official_url"], "intake_year": program["intake_year"],
        "verified_at": program["verified_at"],
        "key_facts": [f for f in key_facts if f["value"]],
        "sources": list(dict.fromkeys([*_sources(program, "duration_ft_months", "total_credits", "intake_months"),
                                       *([window["source_url"]] if window and window.get("source_url") else []),
                                       *([tuition["source_url"]] if tuition and tuition.get("source_url") else [])])),
    }


def _curriculum(program: dict) -> dict:
    electives = knowledge.list_course_electives()
    groups: dict[str, list] = {"core_mandatory": [], "core_choice": [], "capstone": []}
    verticals: dict[str, list] = {}
    for course in knowledge.list_courses():
        code = course["course_code"]
        role = course_recommendation.requirement_role(code, electives.get(code, []))
        item = {"code": code, "title": course["title"], "units": int(course["module_credit"] or 0),
                "description": _short(course["description"])}
        if role in groups:
            groups[role].append(item)
        for vertical in electives.get(code, []):
            verticals.setdefault(vertical, []).append(item)
    for items in (*groups.values(), *verticals.values()):
        items.sort(key=lambda c: c["code"])
    return {
        # The official wording of each rule (knowledge course_rules, current intake).
        "rules": [rule["content"] for rule in knowledge.list_curriculum_rules()],
        "core_mandatory": groups["core_mandatory"],
        "core_choice": groups["core_choice"],
        "capstone": groups["capstone"],
        "verticals": [{"name": name, "courses": courses} for name, courses in sorted(verticals.items())],
        "skill_areas": [
            {"skill": _SKILLS.get(a["skill_id"], a["skill_id"]), "coverage": _COVERAGE.get(a["coverage"], a["coverage"]),
             "courses": a["evidence_courses"]}
            for a in sorted(program["curriculum"], key=lambda a: list(_COVERAGE).index(a["coverage"])
                            if a["coverage"] in _COVERAGE else len(_COVERAGE))
        ],
        "sources": list(dict.fromkeys(a["source_url"] for a in program["curriculum"] if a.get("source_url"))),
    }


def _admissions(program: dict) -> dict:
    facts = program["facts"]
    english = []
    if facts.get("toefl_ibt_min"):
        english.append(f"TOEFL iBT {int(facts['toefl_ibt_min'])}")
    if facts.get("ielts_min"):
        english.append(f"IELTS {float(facts['ielts_min']):.1f}")
    requirements = [
        {"label": "Academic background", "value": facts.get("background_requirement")},
        {"label": "Programming", "value": facts.get("notes")},
        {"label": "English", "value": " or ".join(english) + (f". {facts['english_waiver']}" if facts.get("english_waiver") else "")
         if english else facts.get("english_waiver")},
        {"label": "GMAT / GRE", "value": " — ".join(filter(None, [_GMAT_GRE.get(facts.get("gmat_gre_policy")),
                                                                 facts.get("gmat_gre_note")])) or None},
        {"label": "Work experience", "value": _WORK_EXPERIENCE.get(facts.get("work_exp_policy"))},
        {"label": "Application fee", "value": _money(facts.get("application_fee"), facts.get("application_fee_currency"))},
    ]
    window = next(iter(program["deadlines"]), None)
    documents = [{"label": item["label"], "description": item["description"], "required": item["required"]}
                 for item in knowledge.list_admissions_items().values()]
    documents.sort(key=lambda d: (not d["required"], d["label"] or ""))
    return {
        "requirements": [r for r in requirements if r["value"]],
        "application_window": {"label": window["round_label"], "opens_on": window["opens_on"],
                               "closes_on": window["closes_on"]} if window else None,
        "documents": documents,
        "sources": list(dict.fromkeys([
            *_sources(program, "background_requirement", "notes", "toefl_ibt_min", "english_waiver", "gmat_gre_policy",
                      "application_fee"),
            *([window["source_url"]] if window and window.get("source_url") else []),
        ])),
    }


def _fees(program: dict) -> dict:
    tuition = [{"label": "Tuition" if f["student_category"] == "all" else f"Tuition ({f['student_category']})",
                "amount": _money(f["amount"], f["currency"]), "includes_tax": f["includes_tax"], "note": f["note"]}
               for f in program["fees"]]
    funding = []
    for f in program["funding"]:
        amount = f"{float(f['percent']):g}% of tuition" if f.get("percent") else _money(f.get("amount"), f.get("currency"))
        funding.append({
            "name": f["name"], "kind": f["kind"].replace("_", " ").capitalize(), "amount": amount,
            "for": ", ".join(_FUNDING_FOR.get(c, c) for c in f["eligible_categories"]) if f["eligible_categories"] else None,
            "conditions": f["conditions"], "source_url": f["source_url"],
        })
    return {
        "tuition": tuition, "funding": funding,
        "sources": list(dict.fromkeys([*(f["source_url"] for f in program["fees"] if f.get("source_url")),
                                       *(f["source_url"] for f in funding if f.get("source_url"))])),
    }


def _careers() -> list[dict]:
    titles = {c["course_code"]: c["title"] for c in knowledge.list_courses()}
    by_tag: dict[str, list[str]] = {}
    for code, tags in knowledge.list_course_tags().items():
        for tag in tags:
            by_tag.setdefault(tag, []).append(code)
    return [
        {"name": role["name_en"], "description": role["definition"],
         "skills": [_SKILLS.get(s, s) for s in role["required_skills"]],
         "courses": [{"code": code, "title": titles.get(code)} for code in sorted(by_tag.get(role["tag"], []))]}
        for role in knowledge.list_role_tags()
    ]


def _build() -> dict:
    program = next(p for p in program_catalog.list_programs() if p["is_target"])
    return {
        "programme": _overview(program),
        "curriculum": _curriculum(program),
        "admissions": _admissions(program),
        "fees": _fees(program),
        "careers": _careers(),
        "stories": alumni.showcase_stories(),
    }


def get_page(signed_in: bool) -> dict:
    """The page's content; alumni are named only for signed-in readers."""
    if _cache["page"] is None or time.monotonic() - _cache["at"] > _CACHE_SECONDS:
        _cache["page"] = _build()
        _cache["at"] = time.monotonic()
    page = _cache["page"]
    if signed_in:
        return page
    return {**page, "stories": [{**story, "name": None} for story in page["stories"]]}
