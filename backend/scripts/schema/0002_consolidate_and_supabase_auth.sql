-- Consolidates the backend onto a single Supabase project
-- (postgres.duljjnofpoysswsivyzd) and switches account/password storage to
-- Supabase Auth (auth.users) instead of a self-managed password_hash
-- column. Additive only — nothing in the pre-existing `student` schema
-- (applications, cases, episodic_memory, academic_records,
-- completed_modules, application_status_history, programs, session_state,
-- application_checklist_items) is touched: those tables were already built
-- for the alumni_match/application_tracker/escalation domains this app
-- hasn't implemented yet, and already assume auth.users as the identity
-- source, so nothing here conflicts with them.

-- 1) Extension table for the fields current code needs alongside identity
-- (email/full_name/role/account_status) that Supabase's own auth.users
-- doesn't carry as queryable columns. user_id is NOT independently
-- generated — it must equal the auth.users.id Supabase already issued.
create table if not exists student.users (
    user_id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    full_name text not null,
    account_status text not null default 'active',
    role text not null check (role in ('applicant', 'enrolled_student', 'admin')),
    last_login_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 2) student.user_profiles already exists here (near-identical to
-- PROFILE_FIELDS in app/domains/profile/constants.py) but is missing the
-- one column the résumé-extraction/profile-edit flow writes.
alter table student.user_profiles
    add column if not exists completed_courses text[];

-- 3) The existing student.application_checklist_items is a different,
-- incompatible design (keyed by application_id + item_key, part of a
-- fuller applications workflow this app doesn't implement yet). The
-- checklist domain needs its own simple per-user-item state table, so this
-- is a new table rather than repurposing that one.
create table if not exists student.checklist_items (
    user_id uuid not null references auth.users(id) on delete cascade,
    item_id text not null,
    status text not null default 'not_started',
    evidence_source text,
    note text,
    file_name text,
    content_type text,
    file_size integer,
    storage_path text,
    uploaded_at timestamptz,
    updated_at timestamptz not null default now(),
    primary key (user_id, item_id)
);

-- 4) Block-based incremental conversation-summarization storage (see
-- app/orchestrator/conversation_repository.py / conversation_service.py).
-- No naming collision in this project's student schema (the existing
-- session_state table is a different, single-active-session design), so
-- these are created fresh, matching the orchestrator's SQL exactly.
create table if not exists student.conversations (
    conversation_id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    turn_count integer not null default 0,
    last_frozen_end integer not null default 0,
    raw_tail jsonb not null default '[]'::jsonb,
    history_summaries jsonb not null default '[]'::jsonb,
    pending_turn_intents jsonb not null default '[]'::jsonb,
    total_messages integer not null default 0,
    status text not null default 'normal',
    status_updated_at timestamptz not null default now()
);

create table if not exists student.messages (
    conversation_id uuid primary key references student.conversations(conversation_id) on delete cascade,
    archived_blocks jsonb not null default '[]'::jsonb,
    turn_intents jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now()
);

-- Helpful for turn_service.py's list_sessions()/history lookups.
create index if not exists idx_conversations_user_id on student.conversations (user_id);
