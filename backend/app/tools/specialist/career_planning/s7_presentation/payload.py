"""
S7 — the render view: the part of the domain result the reply is written
from, with every fact in display form. The domain result also carries
audit data (stage results, diagnostics, evidence points) meant for logs
and API callers; that stays out of the view.

Evidence reads as the profile shows it ("Programming proficiency: Has
built a complete project with tests"), courses as "FT5005 Machine
Learning for Finance", skills and roles by their English names. Pure:
labels come from what prefetch gathered.
"""

from __future__ import annotations

from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched

SKILL_NAMES = {
    "ai_ml": "machine learning & AI",
    "data_analytics": "data analytics",
    "data_engineering": "data engineering",
    "finance": "finance",
    "payments_systems": "payments & blockchain systems",
    "product": "product & business",
    "programming": "programming",
    "regulation": "regulation & compliance",
    "risk_modeling": "risk modelling",
    "security": "security",
}


def _skills(names) -> list[str]:
    return [SKILL_NAMES.get(s, s) for s in names]


def _course(code: str, titles: dict[str, str]) -> str:
    return f"{code} {titles[code]}" if code in titles else code


def _evidence_line(item: dict, prefetched: Prefetched, titles: dict[str, str]) -> str:
    if item["source"] == "courses":
        courses = ", ".join(_course(c, titles) for c in item["values"])
        return f"Courses {'in progress' if item['in_progress'] else 'completed'}: {courses}"
    labels = prefetched.evidence_labels.get(item["source"], {})
    values = ", ".join(labels.get("values", {}).get(v, v) for v in item["values"])
    line = f"{labels.get('label', item['source'])}: {values}"
    return line + " (internship only)" if item["internship"] else line


def _role(fit: dict, titles: dict[str, str]) -> dict:
    support = fit["support"]
    return {
        "role": fit["role"]["name"],
        "definition": fit["role"]["definition"],
        "fit_percent": round(fit["fit"] * 100),
        "low_confidence": fit["low_confidence"],
        "in_your_profile": fit["preferred"],
        "skills_met": _skills(fit["met_skills"]),
        "skills_partial": _skills(fit["partial_skills"]),
        "skills_missing": _skills(fit["missing_skills"]),
        "skills_unknown": _skills(fit["unknown_skills"]),
        "related_work_experience": fit["experience"],
        "programme_courses_for_role": len(support["course_codes"]),
        "your_courses_for_role": [_course(c, titles) for c in support["taken"]],
        "your_current_courses_for_role": [_course(c, titles) for c in support["taking"]],
    }


def _roadmap(roadmap: dict | None) -> dict | None:
    if not roadmap:
        return None
    return {
        "graduation_term": roadmap["graduation_term"],
        "graduation_estimated": roadmap["graduation_estimated"],
        "phases": [
            {
                "name": phase["name"],
                "from": phase["start"],
                "to": phase["end"],
                "actions": [a["text"] for a in phase["actions"]],
                "milestones": [
                    {"date": m["on"], "what": m["label"], "projected": m["projected"]}
                    for m in phase["milestones"]
                ],
            }
            for phase in roadmap["phases"]
        ],
    }


def to_render_view(result: dict, prefetched: Prefetched) -> dict:
    titles = {link["code"]: link["title"] for link in prefetched.course_links}
    names = {r["tag"]: r["name"] for r in prefetched.role_catalog}
    comparison = result.get("comparison")
    return {
        "mode": result["mode"],
        "roles": [_role(fit, titles) for fit in result["roles"]],
        "skills": [
            {
                "skill": SKILL_NAMES.get(s["skill"], s["skill"]),
                "status": s["status"],
                "evidence": [_evidence_line(item, prefetched, titles) for item in s["evidence"]],
            }
            for s in result["skills"]
        ],
        "roadmap": _roadmap(result.get("roadmap")),
        "comparison": {
            "needed_by_all": _skills(comparison["shared_skills"]),
            "needed_only_by": {names.get(t, t): _skills(s) for t, s in comparison["distinct_skills"].items() if s},
        } if comparison else None,
        "notes": result.get("notes", []),
        "sources": result.get("sources", []),
    }
