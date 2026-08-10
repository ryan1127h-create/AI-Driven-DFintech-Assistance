-- Restructures `student.messages` from one-row-per-message into
-- one-row-per-conversation, mirroring `student.conversations`. Each freeze
-- (see repository.py::SupabaseConversationStore.archive_block) appends one
-- entry to `archived_blocks` via a single atomic `jsonb ||` UPDATE, instead
-- of inserting a new row per message.
--
-- Why: under concurrent background freeze tasks for the same session (no
-- locking on the freeze decision itself — see maybe_freeze_block), the old
-- one-row-per-message design let a single frozen block get archived
-- redundantly many times over, each redundant attempt inserting a full set
-- of new rows (observed: one block archived 16x, 320 rows for what should
-- have been 20). Appending into one row per conversation via `||` doesn't
-- eliminate redundant freeze decisions (that still needs a compare-and-swap
-- guard on student.conversations.last_frozen_end, not done here), but it
-- does eliminate the row-count blowup: concurrent UPDATEs to the same row
-- serialize through Postgres's normal row locking.
--
-- Old one-row-per-message test data (340 rows, all reproducing the bug
-- above) was truncated — not real conversation content, not migrated.
--
-- Run once against the conversation-storage Supabase project
-- (CONVERSATION_DATABASE_URL), same project/schema as
-- student_conversations_alter.sql.

truncate table student.messages;

alter table student.messages
  drop column sender_type,
  drop column message_text,
  drop column detected_intent,
  drop column sentiment,
  drop column token_count;

-- message_id was the old per-message PK; conversation_id becomes the new
-- one-row-per-conversation PK instead (dropping message_id's PK constraint
-- along with the column, per the ALTER above).
alter table student.messages drop column message_id;
alter table student.messages add primary key (conversation_id);

alter table student.messages
  add column archived_blocks jsonb not null default '[]'::jsonb,
  add column updated_at timestamptz not null default now();
-- created_at is unchanged from the original clone (already `timestamptz
-- default now()`) — now means "when this conversation's archive row was
-- first created". updated_at is bumped on every subsequent append (see
-- archive_block()).
