"""
The soft factors: what decides how competitive an application is
("Admission to the programme is granted on a competitive basis"). Each
follows a statement on the official pages, and is a strength, worth
strengthening, or unknown — never a reason the application fails.
"""

from __future__ import annotations

from app.domains.specialist.assessment import policy
from app.domains.specialist.assessment.contracts import ApplicantFacts, Requirements
from app.domains.specialist.assessment.models import SoftFactor


def background_fit(facts: ApplicantFacts) -> SoftFactor:
    basis = "The programme looks for backgrounds in computing, financial engineering, finance, statistics or other STEM."
    discipline = facts.degree_discipline_category
    extra = ["a higher degree"] if facts.highest_degree in ("master", "phd") else []
    if discipline is None:
        return SoftFactor("background_fit", "unknown", basis, "Your degree discipline isn't known yet.",
                          source_url=policy.FAQ_PAGE, missing_fields=("degree_discipline_category",))
    if discipline in policy.PREFERRED_MAJORS:
        return SoftFactor("background_fit", "strength", basis,
                          "; ".join([f"discipline: {discipline}", *extra]), source_url=policy.FAQ_PAGE)
    return SoftFactor("background_fit", "improve", basis,
                      "; ".join([f"discipline: {discipline}, outside the preferred backgrounds", *extra]),
                      action="Make your quantitative and technical coursework, projects or work prominent in your CV "
                             "and personal statement.", source_url=policy.FAQ_PAGE)


def relevant_experience(facts: ApplicantFacts) -> SoftFactor:
    basis = ("Work, internship or research experience related to FinTech, AI or data analytics is advantageous "
             "(not required).")
    functions = set(facts.function_experience)
    relevant = sorted(functions & policy.RELEVANT_FUNCTIONS)
    transferable = sorted(functions & policy.TRANSFERABLE_FUNCTIONS)
    research = facts.research_output in policy.RESEARCH_OUTPUTS
    found = [f"experience: {f}" for f in relevant] + (["research output"] if research else [])
    if facts.total_work_years and facts.total_work_years not in policy.NO_WORK:
        found.append(f"{facts.total_work_years} years of full-time work")
    if relevant or research:
        return SoftFactor("relevant_experience", "strength", basis, "; ".join(found), source_url=policy.ADMISSIONS_PAGE)
    if not functions and facts.total_work_years is None and facts.research_output is None:
        return SoftFactor("relevant_experience", "unknown", basis, "Your work and research experience aren't known yet.",
                          source_url=policy.ADMISSIONS_PAGE, missing_fields=("function_experience", "total_work_years"))
    finding = "; ".join([f"experience: {f} (transferable)" for f in transferable] + found) or \
        "No FinTech, AI or data-related experience on file."
    return SoftFactor("relevant_experience", "improve", basis, finding,
                      action="Add a FinTech, AI or data project, internship or research piece — even a self-directed "
                             "one you can show.", source_url=policy.ADMISSIONS_PAGE)


def programming_depth(facts: ApplicantFacts) -> SoftFactor:
    basis = "Programming (especially Python) is used in several core and elective courses."
    level, stack = facts.code_level, facts.tech_stack
    if level is not None and level >= policy.PROGRAMMING_STRENGTH_LEVEL:
        return SoftFactor("programming_depth", "strength", basis, f"programming level {level}"
                          + (f"; tech stack: {', '.join(stack)}" if stack else ""), source_url=policy.FAQ_PAGE)
    if level is None and not stack:
        if facts.degree_discipline_category in policy.COMPUTING:
            return SoftFactor("programming_depth", "strength", basis,
                              f"discipline: {facts.degree_discipline_category}", source_url=policy.FAQ_PAGE)
        return SoftFactor("programming_depth", "unknown", basis, "Your programming level isn't known yet.",
                          source_url=policy.FAQ_PAGE, missing_fields=("code_level",))
    finding = (f"programming level {level}" if level is not None else "") + \
        (f"; tech stack: {', '.join(stack)}" if stack else "")
    return SoftFactor("programming_depth", "improve", basis, finding.strip("; "),
                      action="Build one complete Python project with tests (e.g. a data analysis of a financial "
                             "dataset) and keep it where you can show it.", source_url=policy.FAQ_PAGE)


def quant_foundation(facts: ApplicantFacts) -> SoftFactor:
    basis = "Advanced quantitative study counts towards the preparation asked of non-computing applicants."
    courses = sorted(set(facts.prior_coursework) & policy.QUANT_COURSEWORK)
    level = facts.math_stats_level
    found = [f"coursework: {c}" for c in courses] + ([f"maths & statistics level {level}"] if level else [])
    strong = (level is not None and level >= policy.MATHS_LEVEL) or len(courses) >= 2 \
        or facts.degree_discipline_category in policy.QUANT_DISCIPLINES
    if strong:
        if facts.degree_discipline_category in policy.QUANT_DISCIPLINES:
            found.insert(0, f"discipline: {facts.degree_discipline_category}")
        return SoftFactor("quant_foundation", "strength", basis, "; ".join(found), source_url=policy.FAQ_PAGE)
    if not found:
        return SoftFactor("quant_foundation", "unknown", basis, "Your maths and statistics background isn't known yet.",
                          source_url=policy.FAQ_PAGE, missing_fields=("prior_coursework", "math_stats_level"))
    return SoftFactor("quant_foundation", "improve", basis, "; ".join(found),
                      action="Strengthen probability, statistics and linear algebra — a course with a certificate "
                             "you can list is the clearest evidence.", source_url=policy.FAQ_PAGE)


def finance_foundation(facts: ApplicantFacts) -> SoftFactor:
    basis = "Admitted students typically come from computing, information systems, finance or financial engineering."
    found = []
    if facts.degree_discipline_category in policy.FINANCE_DISCIPLINES:
        found.append(f"discipline: {facts.degree_discipline_category}")
    if facts.finance_level is not None and facts.finance_level >= policy.FINANCE_LEVEL:
        found.append(f"finance level {facts.finance_level}")
    found += [f"coursework: {c}" for c in sorted(set(facts.prior_coursework) & policy.FINANCE_COURSEWORK)]
    found += [f"certification: {c}" for c in sorted(set(facts.certifications) & policy.FINANCE_CERTIFICATIONS)]
    if found:
        return SoftFactor("finance_foundation", "strength", basis, "; ".join(found), source_url=policy.FAQ_PAGE)
    if facts.finance_level is None and facts.degree_discipline_category is None and not facts.prior_coursework:
        return SoftFactor("finance_foundation", "unknown", basis, "Your finance background isn't known yet.",
                          source_url=policy.FAQ_PAGE, missing_fields=("finance_level",))
    return SoftFactor("finance_foundation", "improve", basis,
                      f"finance level {facts.finance_level}" if facts.finance_level else "No finance background on file.",
                      action="Learn the finance basics the programme builds on — markets, valuation and risk — e.g. "
                             "an introductory finance course.", source_url=policy.FAQ_PAGE)


def test_scores(facts: ApplicantFacts, req: Requirements) -> SoftFactor:
    reference = req.gmat_reference
    basis = ("A GMAT/GRE score is not mandatory, but a good one strengthens the application"
             + (f" (generally about {reference} on the GMAT, or the GRE equivalent)." if reference else "."))
    url = req.source_urls.get("gmat_gre", policy.FAQ_PAGE)
    gmat = next((t for t in facts.admission_tests if t.key == "GMAT" and t.score is not None), None)
    gre = next((t for t in facts.admission_tests if t.key in ("GRE", "GATE") and t.score is not None), None)
    if gmat and reference and gmat.score >= reference:
        return SoftFactor("test_scores", "strength", basis, f"GMAT {gmat.score:g}", source_url=url, optional=True)
    if gmat:
        return SoftFactor("test_scores", "improve", basis, f"GMAT {gmat.score:g}",
                          action="Optional: a higher GMAT would add weight; it isn't required.",
                          source_url=url, optional=True)
    if gre:
        return SoftFactor("test_scores", "strength", basis, f"{gre.key} {gre.score:g} on file as supporting evidence",
                          source_url=url, optional=True)
    return SoftFactor("test_scores", "improve", basis, "No GMAT/GRE score on file.",
                      action="Optional: a good GMAT/GRE score can strengthen your application; it isn't required.",
                      source_url=url, optional=True)


def academic_record(facts: ApplicantFacts) -> SoftFactor:
    basis = "There is no minimum GPA, but admission is competitive."
    band = facts.gpa_band
    if band in policy.STRONG_GPA or band in policy.SOLID_GPA:
        return SoftFactor("academic_record", "strength", basis, f"GPA band: {band}", source_url=policy.FAQ_PAGE)
    if band in policy.MODEST_GPA:
        return SoftFactor("academic_record", "improve", basis, f"GPA band: {band}",
                          action="Let other evidence carry more weight — relevant projects, coursework results, "
                                 "experience, or a good GMAT/GRE.", source_url=policy.FAQ_PAGE)
    return SoftFactor("academic_record", "unknown", basis, "Your grades aren't known yet.",
                      source_url=policy.FAQ_PAGE, missing_fields=("gpa_band",))
