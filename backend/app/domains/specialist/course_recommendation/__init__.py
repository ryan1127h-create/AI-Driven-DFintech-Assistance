"""Course recommendation from one complete upstream-agent report.

The report supplies every user fact, resolved role profile, course record,
curriculum rule, and source. This domain performs no profile or knowledge-base
lookups. Recommendations are organised into requirement-driven groups (e.g.
mandatory core, core course choice, an elective Vertical, the Capstone path)
rather than one flat list — see workflow.py and stages/ for the workflow that
produces them. Hard eligibility rules always run before any group is
scored or filled, so every returned course comes from the supplied
candidate catalogue.
"""
