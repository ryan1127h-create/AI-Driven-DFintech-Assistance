-- Cleans up leftover schema from an earlier, fully-reverted RBAC attempt
-- (the code that used it was reverted via `git reset --hard`; the schema
-- itself was never cleaned up — see project history). Verified read-only
-- before writing this: no view or other table depends on student.roles or
-- student.departments, and only 3 of 33 existing student.users rows had
-- role_id/department_id set at all (leftover test accounts from that
-- prior verification pass).
ALTER TABLE student.users
    DROP CONSTRAINT IF EXISTS users_role_id_fkey,
    DROP CONSTRAINT IF EXISTS users_department_id_fkey,
    DROP COLUMN IF EXISTS role_id,
    DROP COLUMN IF EXISTS department_id,
    DROP COLUMN IF EXISTS employee_no,
    DROP COLUMN IF EXISTS job_title;

DROP TABLE IF EXISTS student.roles;
DROP TABLE IF EXISTS student.departments;

-- Fresh, simple role column for the new design: exactly three fixed
-- values, so a CHECK constraint is used instead of a lookup table +
-- foreign key (see domains/auth/schemas.py::SelfRegisterableRole — "admin"
-- is deliberately excluded from self-registration).
ALTER TABLE student.users
    ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'applicant'
        CHECK (role IN ('applicant', 'enrolled_student', 'admin'));

-- One-time manual promotion of the first admin account. Run this
-- separately, after the account below has actually registered (through
-- the normal applicant/enrolled_student signup flow) — there is no
-- self-service admin registration by design.
--
-- update student.users set role = 'admin' where email = 'REPLACE_ME@example.com';
