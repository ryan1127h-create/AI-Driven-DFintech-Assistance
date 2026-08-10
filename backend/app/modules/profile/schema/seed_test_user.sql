-- Seeds the single placeholder identity every module currently operates as,
-- until real auth exists (see app/modules/profile/interface.py::TEST_USER_ID).
-- student.user_profiles.user_id is PK + FK -> student.users(user_id) NOT NULL,
-- so a users row must exist before any profile can be written.
-- Run once against the sandbox `student` schema (CONVERSATION_DATABASE_URL).

insert into student.users (user_id, email, full_name, account_status)
values ('55d56a67-4502-495d-b477-7db602850918', 'test.user@example.com', 'Test User', 'active')
on conflict (user_id) do nothing;
