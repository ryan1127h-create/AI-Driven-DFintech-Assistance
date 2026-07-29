-- Run this once against the conversation-storage Supabase project (NOT the
-- read-only Dfintech-agent-db knowledge base project).
--
-- Phase 6 redesign: split into a "hot" table that stays small forever
-- (bounded raw tail + growing-but-small summary list + scalars) and a
-- "cold" append-only archive that holds the full raw messages of blocks
-- once they've been frozen into a summary — the archive is never read on
-- the per-turn hot path, only written once per freeze, kept for audit.

drop table if exists conversation_archive;
drop table if exists conversations;

create table conversations (
  session_id        text primary key,
  turn_count        integer not null default 0,
  last_frozen_end   integer not null default 0,   -- turn number history is frozen up to
  raw_tail          jsonb not null default '[]',   -- unfrozen recent messages only, always bounded
  history_summaries jsonb not null default '[]',   -- [{start_turn,end_turn,summary,created_at}, ...]
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table conversation_archive (
  id           bigint generated always as identity primary key,
  session_id   text not null references conversations(session_id) on delete cascade,
  start_turn   integer not null,
  end_turn     integer not null,
  raw_messages jsonb not null,
  frozen_at    timestamptz not null default now()
);
create index conversation_archive_session_id_idx on conversation_archive (session_id);
