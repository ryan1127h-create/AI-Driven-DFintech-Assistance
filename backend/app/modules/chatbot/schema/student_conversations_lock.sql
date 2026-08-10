-- Adds a per-conversation lock so freeze eligibility can be checked and
-- claimed synchronously (in run_turn/api.py) while the actual summarization
-- work still runs in a background task — see
-- repository.py::ConversationStore.{is_locked,try_lock_for_freeze,unlock_after_freeze}
-- and conversation_service.py::{should_freeze,freeze_and_unlock}.
--
-- Why: without this, concurrent background freeze tasks for the same
-- session could each independently decide "this block needs freezing" off
-- a stale read, redundantly re-doing the work and racing on which one's
-- state update survives (see student_messages_restructure.sql for the
-- related archive-table fix — that fixed row-count blowup but not this).
--
-- status_updated_at backs a TTL-based staleness check (see
-- settings.freeze_lock_ttl_seconds) so a crashed/hung background task can't
-- permanently wedge a conversation.
--
-- Run once against the conversation-storage Supabase project
-- (CONVERSATION_DATABASE_URL), same project/schema as the other
-- student_conversations_*.sql / student_messages_*.sql files in this folder.

alter table student.conversations
  add column status varchar(20) not null default 'normal',
  add column status_updated_at timestamptz not null default now();
