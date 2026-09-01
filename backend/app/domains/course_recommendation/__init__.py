"""
Course recommendation — resolves a target role (from the request, the
applicant's stored profile, or free text) into a set of skill gaps against
the course catalogue, then selects a shortlist of courses to close them.
Excludes completed courses and preclusion conflicts before any selection
happens, so the candidate pool is always valid regardless of how the pick
within it is made. Consumed by career_planning and program_comparison for
their own course-aware output.
"""
