"""
Where an application's admissions document stands, from the school's
checklist row, the application status and the applicant's degree. One
rule for every reader (the checklist page, reminders, the chat's profile
summary, the staff views; the staff dashboard counts outstanding documents
the same way in SQL):

- received:   the school has it.
- missing:    a required document not received while the application is
              still open.
- optional:   not received, and not required for everyone (GRE scores are
              supporting evidence; an English test when we don't know how
              the degree was taught); never counted as missing.
- exempt:     not received, and this applicant doesn't need it (an English
              test after an English-medium degree).
- not_needed: not received, but the application has been decided.

The English test (english_proficiency) is required exactly when the
bachelor's degree wasn't taught mainly in English (profile field
english_medium_degree; program.facts.english_waiver). Every other document
follows the admissions catalogue's flag (knowledge_retrieval), which the
caller passes in.
"""

from __future__ import annotations

# Statuses after which the school no longer waits for documents.
DECIDED_STATUSES = ("OFFER", "ACCEPTED", "REJECTED")

DOCUMENT_STATES = ("missing", "received", "optional", "exempt", "not_needed")

ENGLISH_TEST_KEY = "english_proficiency"


def document_state(
    application_status: str | None, item_key: str, submitted: bool, catalogue_required: bool,
    english_medium_degree: bool | None = None,
) -> str:
    if submitted:
        return "received"
    # Exempt is about the applicant, so it holds whatever the status.
    if item_key == ENGLISH_TEST_KEY and english_medium_degree:
        return "exempt"
    if application_status in DECIDED_STATUSES:
        return "not_needed"
    return "missing" if required_for(item_key, catalogue_required, english_medium_degree) else "optional"


def required_for(item_key: str, catalogue_required: bool, english_medium_degree: bool | None = None) -> bool:
    """Whether this applicant has to send the document at all (the
    English test only after a degree not taught in English)."""
    if item_key == ENGLISH_TEST_KEY and english_medium_degree is not None:
        return not english_medium_degree
    return catalogue_required
