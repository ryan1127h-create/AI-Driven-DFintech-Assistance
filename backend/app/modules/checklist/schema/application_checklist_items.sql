-- R5-A checklist persistence table.
-- Stores per-user checklist status. It is intentionally separate from
-- student.application_documents because the current backend still has no real
-- authenticated application/submission flow.

create table if not exists student.application_checklist_items (
  checklist_item_id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  item_id varchar(80) not null,
  status varchar(50) not null default 'not_started',
  evidence_source varchar(160),
  note text,
  file_name varchar(255),
  content_type varchar(100),
  file_size integer,
  storage_path text,
  file_content bytea,
  uploaded_at timestamp with time zone,
  updated_at timestamp with time zone default now(),
  constraint application_checklist_items_pkey primary key (checklist_item_id),
  constraint application_checklist_items_user_item_key unique (user_id, item_id),
  constraint application_checklist_items_user_id_fkey
    foreign key (user_id) references student.users(user_id),
  constraint application_checklist_items_status_check
    check (status in ('unknown', 'not_started', 'in_progress', 'completed', 'not_applicable'))
);

create index if not exists idx_application_checklist_items_user
  on student.application_checklist_items using btree (user_id);

alter table student.application_checklist_items
  add column if not exists file_name varchar(255),
  add column if not exists content_type varchar(100),
  add column if not exists file_size integer,
  add column if not exists storage_path text,
  add column if not exists file_content bytea,
  add column if not exists uploaded_at timestamp with time zone;
