"""
The hard conditions: what an application must meet — the degree, the
programming or quantitative preparation asked of non-computing applicants,
English, and applying in time. Each is met, not needed, to confirm, or a
gap, decided from the facts alone; nothing unknown is ever called a gap.
"""

from __future__ import annotations

from datetime import date

from app.domains.specialist.assessment import policy
from app.domains.specialist.assessment.contracts import ApplicantFacts, Requirements, TestScore
from app.domains.specialist.assessment.models import HardCheck


def _fmt(score: float) -> str:
    return f"{score:g}"


def _date(d: date) -> str:
    return d.isoformat()


def degree(facts: ApplicantFacts) -> HardCheck:
    requirement = ("A bachelor's degree in computing, or in a related discipline (STEM, finance, economics, "
                   "statistics or business); other qualifications are considered case by case.")
    discipline, highest = facts.degree_discipline_category, facts.highest_degree
    missing = tuple(k for k, v in (("degree_discipline_category", discipline), ("highest_degree", highest)) if v is None)
    if discipline is None:
        return HardCheck("degree", "to_confirm", requirement, "Your degree discipline isn't known yet.",
                         source_url=policy.ADMISSIONS_PAGE, missing_fields=missing)
    if highest == "other":
        return HardCheck("degree", "to_confirm", requirement,
                         "Your highest qualification isn't a bachelor's, master's or PhD, so it would be considered "
                         "case by case.",
                         action="Check with the programme whether your qualification is accepted.",
                         source_url=policy.ADMISSIONS_PAGE)
    if discipline in policy.COMPUTING or discipline in policy.RELATED:
        group = "computing" if discipline in policy.COMPUTING else "related"
        return HardCheck("degree", "met", requirement, f"discipline: {discipline} ({group})",
                         source_url=policy.ADMISSIONS_PAGE, missing_fields=missing)
    return HardCheck("degree", "to_confirm", requirement,
                     f"discipline: {discipline}, outside the listed disciplines, so it is considered case by case.",
                     action="Show strong programming or quantitative evidence to support a case-by-case review.",
                     source_url=policy.ADMISSIONS_PAGE)


def programming_or_quant(facts: ApplicantFacts) -> HardCheck:
    requirement = ("Non-computing applicants must show Python programming knowledge and/or advanced "
                   "quantitative study.")
    discipline = facts.degree_discipline_category
    if discipline in policy.COMPUTING:
        return HardCheck("programming_or_quant", "exempt", requirement,
                         f"discipline: {discipline} (computing) — not asked of computing graduates",
                         source_url=policy.ADMISSIONS_PAGE)

    programming = []
    if facts.code_level is not None and facts.code_level >= policy.PROGRAMMING_LEVEL:
        programming.append(f"programming level {facts.code_level}")
    if "python" in facts.tech_stack:
        programming.append("Python in your tech stack")
    programming += [f"coursework: {c}" for c in sorted(set(facts.prior_coursework) & policy.PROGRAMMING_COURSEWORK)]
    quant = []
    if discipline in policy.QUANT_DISCIPLINES:
        quant.append(f"discipline: {discipline}")
    if facts.math_stats_level is not None and facts.math_stats_level >= policy.MATHS_LEVEL:
        quant.append(f"maths & statistics level {facts.math_stats_level}")
    quant += [f"coursework: {c}" for c in sorted(set(facts.prior_coursework) & policy.QUANT_COURSEWORK)]

    if programming or quant:
        return HardCheck("programming_or_quant", "met", requirement, "; ".join(dict.fromkeys(programming + quant)),
                         source_url=policy.ADMISSIONS_PAGE)
    # Either kind of evidence meets the condition, so it is a gap only when
    # both are known to be missing; with one side unknown it is to confirm.
    programming_known = facts.code_level is not None or bool(facts.prior_coursework)
    quant_known = facts.math_stats_level is not None or bool(facts.prior_coursework)
    action = ("Build Python evidence before applying — e.g. a course plus a small data-processing project you "
              "can show — or document advanced quantitative coursework.")
    if programming_known and quant_known:
        return HardCheck("programming_or_quant", "gap", requirement,
                         "No Python programming or advanced quantitative evidence"
                         + (f" (programming level {facts.code_level})" if facts.code_level is not None else "") + ".",
                         action=action, source_url=policy.ADMISSIONS_PAGE)
    missing = tuple(k for k in ("prior_coursework", "code_level", "math_stats_level", "degree_discipline_category")
                    if getattr(facts, k) in (None, []))
    known = f" (programming level {facts.code_level})" if facts.code_level is not None else ""
    return HardCheck("programming_or_quant", "to_confirm", requirement,
                     f"No Python evidence on file{known}, and your quantitative coursework isn't known yet.",
                     action=action if facts.code_level is not None else "",
                     source_url=policy.ADMISSIONS_PAGE, missing_fields=missing)


def _valid_on(test: TestScore, day: date) -> bool | None:
    if test.test_date is None:
        return None
    years = policy.TEST_VALIDITY_YEARS[test.key]
    try:
        expires = test.test_date.replace(year=test.test_date.year + years)
    except ValueError:  # 29 February
        expires = test.test_date.replace(year=test.test_date.year + years, day=28)
    return day <= expires


def _meets(test: TestScore, req: Requirements) -> bool | None:
    if test.score is None:
        return None
    if test.key == "IELTS":
        return None if req.ielts_min is None else test.score >= req.ielts_min
    # TOEFL: the 1-6 band scale from January 2026, or the 0-120 scale before it.
    if test.score <= policy.TOEFL_BAND_MAX:
        return None if req.toefl_band_min is None else test.score >= req.toefl_band_min
    return None if req.toefl_ibt_min is None else test.score >= req.toefl_ibt_min


def english(facts: ApplicantFacts, req: Requirements, deadline: date) -> HardCheck:
    minimums = " / ".join(x for x in (
        f"TOEFL iBT {req.toefl_ibt_min}" if req.toefl_ibt_min else "",
        f"{_fmt(req.toefl_band_min)} on the TOEFL 1-6 scale" if req.toefl_band_min else "",
        f"IELTS {_fmt(req.ielts_min)}" if req.ielts_min else "") if x)
    requirement = (f"Applicants whose degree wasn't taught mainly in English need {minimums}, "
                   f"valid for 2 years.")
    url = req.source_urls.get("english", policy.ADMISSIONS_PAGE)
    if facts.english_medium_degree:
        return HardCheck("english", "exempt", requirement, "Your degree was taught in English.", source_url=url)

    tests = [t for t in facts.admission_tests if t.key in policy.ENGLISH_TESTS]
    passing = [t for t in tests if _meets(t, req)]
    for test in passing:
        if _valid_on(test, deadline) is not False:
            note = "" if test.test_date else " (test date not on file — check it is within 2 years)"
            return HardCheck("english", "met", requirement, f"{test.key} {_fmt(test.score)} meets the minimum{note}",
                             source_url=url)
    if passing:
        test = passing[0]
        return HardCheck("english", "gap", requirement,
                         f"{test.key} {_fmt(test.score)} (taken {_date(test.test_date)}) will be over 2 years old "
                         f"by the {_date(deadline)} deadline.",
                         action="Retake TOEFL or IELTS so the score is valid when you apply.", source_url=url)
    below = [t for t in tests if _meets(t, req) is False]
    if below:
        test = below[0]
        return HardCheck("english", "gap", requirement, f"{test.key} {_fmt(test.score)} is below the minimum.",
                         action=f"Retake to reach {minimums}.", source_url=url)
    if facts.english_medium_degree is False:
        return HardCheck("english", "gap", requirement, "Your degree wasn't taught in English and no TOEFL/IELTS "
                         "score is on file.", action=f"Take TOEFL or IELTS and reach {minimums}.", source_url=url)
    return HardCheck("english", "to_confirm", requirement,
                     "Whether your degree was taught in English, and any TOEFL/IELTS score, aren't known yet.",
                     source_url=url, missing_fields=("english_medium_degree", "admission_tests"))


def timing(req: Requirements, today: date) -> HardCheck:
    url = req.source_urls.get("deadline", "")
    opens, closes = req.application_opens, req.application_closes
    if closes is None:
        return HardCheck("timing", "to_confirm", "Apply within the published application period.",
                         f"The August {req.intake_year} application period isn't published yet.", source_url=url)
    period = (f"{_date(opens)} to " if opens else "until ") + _date(closes)
    requirement = f"Apply within the August {req.intake_year} application period: {period}."
    if today > closes:
        return HardCheck("timing", "to_confirm", requirement,
                         f"The August {req.intake_year} application period closed on {_date(closes)}; the next "
                         "period isn't published yet.", action="Watch the programme's application page for the next "
                         "intake's dates.", source_url=url)
    if opens and today < opens:
        return HardCheck("timing", "met", requirement, f"Applications open on {_date(opens)}.",
                         action=f"Prepare your documents to apply between {period}.", source_url=url)
    return HardCheck("timing", "met", requirement, f"Applications are open now and close on {_date(closes)}.",
                     action=f"Submit by {_date(closes)}; early applicants may be considered for early offers.",
                     source_url=url)
