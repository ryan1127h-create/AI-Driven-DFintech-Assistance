"""
S5 — "which of these suits me?", answered from the applicant's own goals
rather than by ranking the programmes. Runs only when the user asks that
(ComparisonInput.asks_which_suits) and only on what is on file.

Each goal the applicant has is checked across the programmes compared,
from S3's facts and S4's fit, and names the programme(s) ahead on it
(empty: level, or not comparable — e.g. fees in different currencies are
never converted to compare them):

  target_role  more of the target role's skills in everyone's required
               courses (fewer not taught breaks a tie)
  english      the applicant's English score meets the minimum
  work         the applicant's work experience meets the minimum
  and, among the profile's decision factors:
  duration     the shorter full-time programme
  flexibility  part-time study offered
  tech_depth / finance_depth
               more technology / finance skills everyone is taught
  cost         lower cost for this applicant, same currency only
  scholarship  more reductions open to this applicant

The summary counts, per programme, the goals it is ahead on (sharing the
lead counts too), and names a lead only when one programme is ahead on
strictly more goals than any other; otherwise the goals split. It is a count over the applicant's stated goals, never an
overall verdict: reputation, rankings and anything not on file aren't in
it, and the reply says so.
"""

from __future__ import annotations

from app.domains.specialist.program_comparison.models import Applicant, ApplicantFit, ProgramView

# No barrier for the applicant: met, waived, or no minimum to meet
# ("preferred" work experience has none).
_MEETS = {"met", "waived", "not_required", "preferred"}


def _ahead(values: dict[str, float]) -> list[str]:
    """The programmes with the highest value, unless all are level."""
    if len(values) < 2 or len(set(values.values())) == 1:
        return []
    best = max(values.values())
    return [pid for pid, value in values.items() if value == best]


def _goal(goal: str, shown: dict[str, str], scores: dict[str, float]) -> dict | None:
    if len(shown) < 2:
        return None
    return {"goal": goal, "values": shown, "ahead": _ahead(scores)}


def _target_role(fits: dict[str, ApplicantFit]) -> dict | None:
    shown, scores = {}, {}
    for pid, fit in fits.items():
        target = fit.by_dimension.get("curriculum", {}).get("target")
        if not target:
            continue
        total = len(target["guaranteed"]) + len(target["available"]) + len(target["not_taught"]) + len(target["unknown"])
        shown[pid] = (f"{len(target['guaranteed'])} of {total} target-role skills in required courses, "
                      f"{len(target['not_taught'])} not taught")
        scores[pid] = len(target["guaranteed"]) - len(target["not_taught"]) / 100
    return _goal("target_role", shown, scores)


def _requirement(goal: str, key: str, fits: dict[str, ApplicantFit]) -> dict | None:
    shown, scores = {}, {}
    for pid, fit in fits.items():
        check = fit.by_dimension.get("admission", {}).get(key)
        if not check or check["status"] in ("no_data", "unknown", "missing"):
            continue
        shown[pid] = check["status"]
        scores[pid] = 1.0 if check["status"] in _MEETS else 0.0
    return _goal(goal, shown, scores)


def _duration(views: dict[str, ProgramView]) -> dict | None:
    months = {pid: v.raw_facts.get("duration_ft_months") for pid, v in views.items()}
    months = {pid: m for pid, m in months.items() if m}
    return _goal("duration", {pid: f"{m:g} months full-time" for pid, m in months.items()},
                 {pid: -m for pid, m in months.items()})


def _flexibility(views: dict[str, ProgramView]) -> dict | None:
    modes = {pid: v.raw_facts.get("study_modes") for pid, v in views.items() if v.raw_facts.get("study_modes")}
    return _goal("flexibility", {pid: "part-time offered" if "part_time" in m else "full-time only" for pid, m in modes.items()},
                 {pid: 1.0 if "part_time" in m else 0.0 for pid, m in modes.items()})


def _depth(side: str, fits: dict[str, ApplicantFit]) -> dict | None:
    shown, scores = {}, {}
    for pid, fit in fits.items():
        depth = fit.by_dimension.get("curriculum", {}).get(f"{side}_depth")
        if depth is not None:
            shown[pid] = f"{len(depth['guaranteed'])} {side} skills everyone is taught"
            scores[pid] = len(depth["guaranteed"])
    return _goal(f"{side}_depth", shown, scores)


def _cost(views: dict[str, ProgramView], fits: dict[str, ApplicantFit]) -> dict | None:
    amounts = {}
    for pid, view in views.items():
        cost = fits[pid].by_dimension.get("cost", {}) if pid in fits else {}
        fees = [f for f in view.fees if f["basis"] == "programme"]
        if "net_amount" in cost:
            amounts[pid] = (cost["net_amount"], cost["currency"])
        elif len(fees) == 1:
            amounts[pid] = (fees[0]["amount"], fees[0]["currency"])
    if len(amounts) < 2:
        return None
    shown = {pid: f"{currency} {amount:,.0f}" for pid, (amount, currency) in amounts.items()}
    if len({currency for _, currency in amounts.values()}) > 1:
        return {"goal": "cost", "values": shown, "ahead": [], "not_comparable": "different currencies"}
    return _goal("cost", shown, {pid: -amount for pid, (amount, _) in amounts.items()})


def _scholarship(fits: dict[str, ApplicantFit]) -> dict | None:
    shown, scores = {}, {}
    for pid, fit in fits.items():
        cost = fit.by_dimension.get("cost")
        if cost is None:
            continue
        count = bool(cost.get("deduction")) + sum(1 for r in cost.get("other_reductions", []) if r.get("eligible") is not False)
        shown[pid] = f"{count} fee reduction(s) or scholarship(s) open to you"
        scores[pid] = count
    return _goal("scholarship", shown, scores)


def check(views: dict[str, ProgramView], fits: dict[str, ApplicantFit], applicant: Applicant) -> dict | None:
    """{goals: [{goal, values: {program_id: text}, ahead: [program_id], not_comparable?}],
    ahead_count: {program_id: goals it is ahead on}, lead: program_id | None}, or None when
    nothing on file can be compared."""
    factors = set(applicant.decision_factors)
    candidates = [
        _target_role(fits),
        _requirement("english", "english", fits),
        _requirement("work_experience", "work", fits),
        _duration(views) if "duration" in factors else None,
        _flexibility(views) if "flexibility" in factors else None,
        _depth("tech", fits) if "tech_depth" in factors else None,
        _depth("finance", fits) if "finance_depth" in factors else None,
        _cost(views, fits) if "cost" in factors else None,
        _scholarship(fits) if "scholarship" in factors else None,
    ]
    goals = [g for g in candidates if g]
    if not goals:
        return None
    counts = {pid: sum(1 for g in goals if pid in g["ahead"]) for pid in views}
    top = max(counts.values())
    leaders = [pid for pid, n in counts.items() if n == top]
    return {"goals": goals, "ahead_count": counts, "lead": leaders[0] if top > 0 and len(leaders) == 1 else None}
