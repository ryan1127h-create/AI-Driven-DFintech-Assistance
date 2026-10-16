"""
The assessment's rules — how profile values map onto MSc DFT's published
admission statements. The figures that change by intake (score minimums,
dates, the GMAT reference) come in the report from the programme
catalogue; what lives here are the readings of the official pages that the
catalogue has no column for, each with the statement it follows.

Pure data, depends on nothing in its domain.
"""

from __future__ import annotations

ADMISSIONS_PAGE = "https://www.comp.nus.edu.sg/programmes/pg/mdft/admissions/"
FAQ_PAGE = "https://www.comp.nus.edu.sg/programmes/pg/mdft/faq/"

# --- degree background ---------------------------------------------------------
# Admission Criteria: "A bachelor's degree in computing; or a bachelor's
# degree in a related discipline (such as STEM, Finance, Economics,
# Statistics or Business)" ... "Candidates with academic qualifications
# other than the above may be considered for admission on a case-by-case
# basis."
COMPUTING = frozenset({"cs_se", "information_systems"})
RELATED = frozenset({"engineering", "math_stats_physics", "finance_econ_accounting", "business_mgmt"})
DEGREES = frozenset({"bachelor", "master", "phd"})

# FAQ (education major): "we are looking for students with background in
# Computing, Financial Engineering, Finance, Statistics, or other STEM."
PREFERRED_MAJORS = frozenset({"cs_se", "information_systems", "engineering", "math_stats_physics",
                              "finance_econ_accounting"})

# --- programming and quantitative preparation -------------------------------------
# Admission Criteria: "non-computing students must provide sufficient
# evidence of python programming knowledge and/or evidence of learning
# advanced quantitative subjects."
# Level 2 of code_level is "Has written data-processing scripts
# independently" — the programme's working Python bar (the same level the
# derived readiness gap uses).
PROGRAMMING_LEVEL = 2
PROGRAMMING_COURSEWORK = frozenset({"programming", "dsa", "databases", "machine_learning"})
QUANT_COURSEWORK = frozenset({"linear_algebra", "probability_statistics", "econometrics", "stochastic_calculus",
                              "machine_learning"})
QUANT_DISCIPLINES = frozenset({"math_stats_physics"})
MATHS_LEVEL = 2  # "Can explain maximum likelihood estimation and hypothesis testing"

# FAQ (programming): knowing a basic programming language "especially
# Python" is advantageous — so beyond the bar, a complete project
# (code_level 3) counts as a strength.
PROGRAMMING_STRENGTH_LEVEL = 3

# --- finance preparation ------------------------------------------------------------
# FAQ (expected knowledge): admitted students typically come from "CS, IS,
# Finance, or Financial Engineering".
FINANCE_DISCIPLINES = frozenset({"finance_econ_accounting"})
FINANCE_COURSEWORK = frozenset({"corporate_finance", "investments_derivatives", "accounting"})
FINANCE_CERTIFICATIONS = frozenset({"cfa", "frm", "cqf"})
FINANCE_LEVEL = 2  # "Can do a DCF valuation"

# --- test scores ----------------------------------------------------------------------
# Test Scores: "The validity of GRE/GMAT and TOEFL/IELTS scores are 5 years
# and 2 years respectively." A score must still be valid when the
# application goes in, so it is checked against the application deadline.
TEST_VALIDITY_YEARS = {"GRE": 5, "GMAT": 5, "GATE": 5, "TOEFL": 2, "IELTS": 2}
ENGLISH_TESTS = ("TOEFL", "IELTS")
# On the new TOEFL iBT 1-6 band scale (from 21 Jan 2026) scores are at most 6.
TOEFL_BAND_MAX = 6

# --- experience -------------------------------------------------------------------------
# Admission Criteria: "Work experiences in FinTech, AI, or Data Analytics
# will be advantageous, but are not required." FAQ: "We also prefer
# candidates with work experience, internship experience, or research
# project experience related to FinTech."
RELEVANT_FUNCTIONS = frozenset({"engineering", "data_ai", "quant", "risk_compliance", "research"})
TRANSFERABLE_FUNCTIONS = frozenset({"product_business", "operations", "sales_client"})
RESEARCH_OUTPUTS = frozenset({"conference", "journal", "multiple_journal"})
NO_WORK = frozenset({"0", "<1"})

# --- academic record ----------------------------------------------------------------------
# FAQ: "There is no minimum GPA requirement" and admission "is competitive
# basis" — so grades are never a hard condition, only a competitive signal.
STRONG_GPA = frozenset({"top_10pct", "first_class_equiv"})
SOLID_GPA = frozenset({"second_upper_equiv"})
MODEST_GPA = frozenset({"second_lower_equiv", "below"})

# --- what to ask for when unknown -----------------------------------------------------------
# The fields that settle a hard condition, most decisive first.
DECISIVE_FIELDS = ("degree_discipline_category", "english_medium_degree", "admission_tests", "code_level",
                   "highest_degree")
