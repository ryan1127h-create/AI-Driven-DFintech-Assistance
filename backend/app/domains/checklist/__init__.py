"""
Checklist — tracks each applicant's admission-document contract items
(transcript, résumé, references, ...) and their per-item completion
status, backed by uploaded files in object storage. The résumé item is the
one other domains care about: profile reads the currently-uploaded résumé
through this domain rather than accepting its own separate upload, so the
two can never disagree about which file is current.
"""
