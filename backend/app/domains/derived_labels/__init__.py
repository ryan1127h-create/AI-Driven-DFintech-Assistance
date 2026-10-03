"""
Derived labels — profile_usability, motivation_segment, readiness_gap,
drop_off_risk and graduation_risk_flags, computed by fixed rules (rules.py)
from the profile, the school's records and the curriculum, and stored on
the profile's derived row. Never shown to the user: readiness gaps and
graduation risks inform course advice (see profile.derived_course_notes);
the rest are kept for staff analytics. Recomputed in the background when a
user's profile changes or they come back, and for everyone by
scripts/compute_derived_labels.py.
"""
