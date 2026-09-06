"""Course recommendation from one complete upstream-agent report.

The report supplies every user fact, resolved role profile, course record,
curriculum rule, and source. This domain performs no profile or knowledge-base
lookups. It applies hard eligibility rules before model or fallback selection,
so every returned course comes from the supplied candidate catalogue.
"""
