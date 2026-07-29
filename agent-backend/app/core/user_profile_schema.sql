-- Run this once against the conversation-storage Supabase project (the
-- same project as conversations, NOT the read-only Dfintech-agent-db).
-- One row per user_id (currently always "user001" — see DEFAULT_USER_ID
-- in app/api/chat.py until real auth exists).

create table if not exists user_profiles (
  user_id    text primary key,
  profile    jsonb not null default '{}',
  updated_at timestamptz not null default now()
);
