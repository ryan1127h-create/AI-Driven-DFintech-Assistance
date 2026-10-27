"""
S5 action wording — what the roadmap tells the student to do for each
kind of gap. Each skill's action is anchored on the profile's level
descriptions (field_definitions.value_labels) where one exists, so a
milestone can be checked against the same scale the student rates
themselves on. The career channels are the ones the programme's FAQ
names (knowledge.document_chunks faq:career_planning_support_provided_students
and faq:find_part_time_job_nus).

English text; the reply is localised at rendering.
"""

from __future__ import annotations

SKILL_ACTIONS: dict[str, str] = {
    "programming": (
        "Build one complete project with tests (programming level 3) and keep it in a portfolio you can show."
    ),
    "ai_ml": (
        "Train a model with cross-validation on a financial dataset, then take one model from data to "
        "deployment (machine-learning levels 2-3)."
    ),
    "data_analytics": (
        "Take one real dataset from question to written conclusion, in an analysis you can walk through "
        "in an interview."
    ),
    "data_engineering": (
        "Build a data pipeline (ETL) on your own, then run one on a distributed or cloud tool such as Spark "
        "(data-engineering levels 2-3)."
    ),
    "finance": (
        "Work up from a DCF valuation to explaining option pricing such as Black-Scholes (finance levels 2-3)."
    ),
    "risk_modeling": (
        "Build a small risk model on a portfolio and document its assumptions and limits."
    ),
    "regulation": (
        "Write a short brief on a regulation that shapes the role and how a firm puts it into practice."
    ),
    "security": (
        "Complete one hands-on security exercise, such as threat-modelling a payment flow, and write it up."
    ),
    "payments_systems": (
        "Write and deploy a smart contract, then build a small decentralised application (blockchain levels 2-3)."
    ),
    "product": (
        "Write a product brief for a FinTech feature (user problem, success metrics, trade-offs) and have a "
        "practitioner review it."
    ),
}

# Skills with no evidence either way: the first step is to record what
# the student has, not to learn it.
EVIDENCE_ACTION = (
    "Add what you have already done in {skills} to your profile, so it can be assessed rather than left unknown."
)

# Programme-readiness areas (profile.derived readiness_gap).
READINESS_ACTIONS: dict[str, str] = {
    "programming": (
        "Before the programme, get to writing data-processing scripts on your own (programming level {required}); "
        "Python is used in several core and elective courses."
    ),
    "maths_stats": (
        "Before the programme, get to explaining maximum likelihood estimation and hypothesis testing "
        "(maths & statistics level {required})."
    ),
    "finance": (
        "Before the programme, learn how markets work and how to read financial statements (finance level {required})."
    ),
}

CAPSTONE_APPLICATION_ACTION = (
    "Apply for Capstone internships through NUS TalentConnect while applications are open, leading with the "
    "evidence you've built for the role."
)
CAPSTONE_INTERNSHIP_ACTION = (
    "Use the internship to produce at least one piece of role evidence you can describe in interviews."
)
JOB_SEARCH_ACTIONS = (
    "Apply through NUS TalentConnect and the Centre for Future Graduates (CFG) job listings, and attend the "
    "career fairs NUS and SoC run.",
    "Practise interviews for the role, using your strongest pieces of evidence as answers.",
)
