-- Adds prior/relevant completed courses to the sandbox profile row.
-- This is for applicant background and recommendation personalisation, not
-- MSc DFT degree-progress tracking.

alter table student.user_profiles
  add column if not exists completed_courses text[] default '{}'::text[];
