-- Adapts the sandbox `student` schema's pre-existing `conversations` /
-- `messages` tables (see app/modules/profile/schema/student_schema_clone.sql)
-- to also serve as the chatbot module's storage, replacing the old
-- `public.conversations` / `public.conversation_archive` tables (see
-- conversation_schema.sql, now legacy).
--
-- `student.conversations` gets the block-summarization bookkeeping columns
-- this module needs (turn_count/last_frozen_end/raw_tail/history_summaries)
-- added on top of its existing columns — `conversation_id` (already the PK)
-- doubles as this module's session_id, no separate column needed.
--
-- `student.messages` needed no structural change (it's already a
-- one-row-per-message table, a good fit for the "cold" archive role
-- conversation_archive used to serve — see repository.py::archive_block),
-- but its FK to conversations defaulted to ON DELETE NO ACTION; changed to
-- CASCADE to match the old conversation_archive's delete-with-parent
-- behavior (see repository.py::delete).
--
-- Run once against the conversation-storage Supabase project
-- (CONVERSATION_DATABASE_URL), same project as student_schema_clone.sql.

alter table student.conversations
  add column turn_count integer not null default 0,
  add column last_frozen_end integer not null default 0,
  add column raw_tail jsonb not null default '[]'::jsonb,
  add column history_summaries jsonb not null default '[]'::jsonb;

alter table student.messages
  drop constraint messages_conversation_id_fkey,
  add constraint messages_conversation_id_fkey
    foreign key (conversation_id) references student.conversations(conversation_id)
    on delete cascade;
