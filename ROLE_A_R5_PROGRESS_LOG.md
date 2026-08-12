# Role A Progress Log: Round 5-A and 5-B

Date: 2026-08-12

Branch:

```text
backend_integration
```

Main branch status:

```text
No changes were pushed to main. Round 5-A work stays on backend_integration.
```

## 1. Round 5 Scope

Round 5 moves checklist from a pure API contract toward a usable backend
foundation and adds per-item file upload.

Scope:

```text
1. Add checklist status persistence.
2. Keep the existing checklist API shape stable.
3. Add a migration file for the database teammate.
4. Add one-file-per-checklist-item upload.
5. Do not implement automatic document content verification yet.
```

## 2. Completed Features

Completed items:

```text
1. Added checklist repository for per-user item status.
2. Added student.application_checklist_items migration SQL.
3. Updated GET /api/v1/checklist to merge persisted state when the table exists.
4. Updated PATCH /api/v1/checklist/items/{item_id} to persist one item update.
5. Added POST /api/v1/checklist/items/{item_id}/file for item-by-item file upload.
6. Added checklist item note, file metadata, uploaded_at, and updated_at fields to the response model.
7. Added unit tests for checklist service logic and upload behavior.
8. Verified compile, full pytest suite, and HTTP behavior.
```

## 3. API Behavior

### 3.1 GET /api/v1/checklist

Current behavior:

```text
If student.application_checklist_items exists:
  - returns implementation_status = "partial"
  - merges saved status/evidence_source/note/updated_at into checklist items

If the table does not exist yet:
  - returns implementation_status = "contract_only"
  - falls back to static checklist definitions
  - does not crash
```

Status behavior:

```text
Default item status is not_started.
Required items not completed or not_applicable are counted in outstanding_required_count.
```

### 3.2 PATCH /api/v1/checklist/items/{item_id}

Request body:

```json
{
  "status": "not_started|in_progress|completed|not_applicable|unknown",
  "evidence_source": "string|null",
  "note": "string|null"
}
```

Current behavior:

```text
If the migration has been applied:
  - creates or updates the item status for the current placeholder user
  - returns the full checklist

If the migration has not been applied:
  - returns 500 with a clear migration-required message

If item_id is unknown:
  - returns 400
```

### 3.3 POST /api/v1/checklist/items/{item_id}/file

Purpose:

```text
Upload one file for one checklist item, such as CV, transcript, TOEFL/IELTS
report, referee evidence, or application fee proof.
```

Current behavior:

```text
1. Validates item_id.
2. Accepts pdf, doc, docx, jpg, jpeg, and png.
3. Rejects empty files.
4. Rejects files larger than 10 MB.
5. Stores the file content in Supabase Postgres under student.application_checklist_items.file_content.
6. Saves file metadata to student.application_checklist_items.
7. Marks the item status as completed.
```

Reason for putting this under checklist:

```text
Profile/resume upload extracts the applicant profile from a resume.
Checklist upload is for application materials. CV, language scores, transcripts,
identity documents, and payment proof belong to checklist/application material
flow, not the profile extraction endpoint.
```

Cloud storage decision:

```text
Files are stored in Supabase Postgres as bytea for the current demo/test phase.
No uploaded checklist file is stored under backend/uploads/ anymore.
For production, Supabase Storage can replace file_content later if a service-role
storage key and bucket policy are provided.
```

## 4. Code Changes

### 4.1 backend/app/modules/checklist/repository.py

Change:

```text
Added list_items(user_id).
Added upsert_item(user_id, item_id, fields).
Added file metadata persistence support.
```

Reason:

```text
Checklist item state needs a small persistence layer instead of staying
contract-only.
```

### 4.2 backend/app/modules/checklist/service.py

Change:

```text
GET now merges persisted checklist state.
PATCH now validates item_id and writes state through repository.
GET falls back cleanly if the migration table is missing.
POST file upload validates and stores one file per checklist item.
```

Reason:

```text
The frontend can start using checklist state once the database migration is
applied, while the endpoint remains safe before migration.
```

### 4.3 backend/app/modules/checklist/api.py

Change:

```text
PATCH /checklist/items/{item_id} no longer returns fixed 501.
It now calls service.patch_checklist_item().
Added POST /checklist/items/{item_id}/file.
```

Reason:

```text
Round 5-A implements the backend persistence contract for checklist item state.
```

### 4.4 backend/app/modules/checklist/schemas.py

Change:

```text
Added note and updated_at to ChecklistItem.
Added file_name, content_type, file_size, and uploaded_at to ChecklistItem.
Kept existing status/evidence_source fields.
```

Reason:

```text
Frontend can show a user/admin note and last update time for each checklist item.
```

### 4.5 backend/app/modules/checklist/schema/application_checklist_items.sql

Change:

```text
Added migration SQL for student.application_checklist_items.
```

Reason:

```text
The current backend has no real authenticated application/submission flow yet,
so checklist state is stored by user_id + item_id instead of application_id.
```

### 4.6 backend/tests/test_checklist_service.py

Change:

```text
Added 4 unit tests for checklist service behavior.
```

Reason:

```text
Checklist logic can be tested without database or LLM access.
```

## 5. Database Impact

New table required:

```text
student.application_checklist_items
```

Migration file:

```text
backend/app/modules/checklist/schema/application_checklist_items.sql
```

SQL summary:

```sql
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
```

Existing Round 3 migration still required:

```sql
alter table student.user_profiles
  add column if not exists completed_courses text[] default '{}'::text[];
```

Database teammate action:

```text
1. Run backend/app/modules/profile/schema/user_profiles_completed_courses.sql.
2. Run backend/app/modules/checklist/schema/application_checklist_items.sql.
```

Execution status on Supabase test project:

```text
Executed by Codex on 2026-08-12 against project cajqvphdrvpbagbcoare
through CONVERSATION_DATABASE_URL.
Re-applied after the cloud-storage change to add file_content bytea.
```

Applied files:

```text
backend/app/modules/profile/schema/seed_test_user.sql
backend/app/modules/profile/schema/user_profiles_completed_courses.sql
backend/app/modules/checklist/schema/application_checklist_items.sql
```

Post-migration schema check:

```text
student.user_profiles.completed_courses exists as text[].
student.application_checklist_items exists.
student.application_checklist_items columns confirmed:
checklist_item_id, user_id, item_id, status, evidence_source, note,
file_name, content_type, file_size, storage_path, file_content, uploaded_at,
updated_at.
```

## 6. Frontend Impact

Frontend can now use:

```text
GET   /api/v1/checklist
PATCH /api/v1/checklist/items/{item_id}
POST  /api/v1/checklist/items/{item_id}/file
```

New response fields on each checklist item:

```text
note
file_name
content_type
file_size
uploaded_at
updated_at
```

Recommended frontend behavior:

```text
1. If implementation_status is contract_only, show checklist as read-only or migration-not-ready.
2. If implementation_status is partial, allow status updates.
3. Upload files one checklist item at a time.
4. Treat outstanding_required_count as meaningful once implementation_status is partial.
```

Still not implemented:

```text
Automatic verification of document content.
Real authenticated user identity beyond TEST_USER_ID.
```

## 7. Verification

Verification performed:

```text
python -m compileall -q app tests
python -m pytest tests/test_checklist_service.py -q
python -m pytest tests -q
GET /api/v1/checklist through FastAPI TestClient
PATCH /api/v1/checklist/items/not_real through FastAPI TestClient
PATCH /api/v1/checklist/items/cv through FastAPI TestClient before migration
POST /api/v1/checklist/items/{item_id}/file through FastAPI TestClient
```

Results:

```text
compileall: passed
checklist tests: 5 passed
full pytest: 43 passed
GET /api/v1/checklist: 200
GET /api/v1/checklist before migration: implementation_status = contract_only
PATCH unknown item: 400
PATCH valid item before migration: 500 with migration-required message
POST file unknown item: 400
POST file valid item before migration: 500 with migration-required message
POST file valid item before migration: failed before cloud persistence, no file written locally
```

Supabase integration test after migration:

```text
GET /api/v1/checklist: 200, implementation_status = partial, outstanding_required_count = 7
PATCH /api/v1/checklist/items/financial_support: 200, persisted state
POST /api/v1/checklist/items/financial_support/file: 200, uploaded metadata persisted
Uploaded item after test: status = completed, file_name = test_support.pdf, file_size = 13
Temporary test DB row for financial_support: deleted after verification
```

Supabase integration test after cloud-storage change:

```text
POST /api/v1/checklist/items/financial_support/file: 200
Uploaded item after test: status = completed, file_name = cloud_support.pdf, file_size = 15
Verified octet_length(file_content) = 15 in student.application_checklist_items
Verified storage_path = supabase-postgres:student.application_checklist_items/<user_id>/financial_support
Temporary test DB row for financial_support: deleted after verification
```

Cleanup note:

```text
The earlier local-storage test file under backend/uploads/checklist/ was a
pre-cloud implementation artifact. Current R5 code no longer writes checklist
uploads locally. A direct deletion command for that old ignored test file was
blocked by the local shell policy, but uploads/ is gitignored and will not be
committed.
```

Known test warning:

```text
FastAPI TestClient printed a StarletteDeprecationWarning about httpx.
This warning did not fail the tests.
```

## 8. Current Status

Current status:

```text
R5-A backend checklist persistence foundation: completed locally
R5-B per-item checklist file upload: completed locally
Database migration execution: completed on Supabase test project cajqvphdrvpbagbcoare
Automatic document content verification: not implemented
Main branch: untouched
backend_integration branch: ready for commit and push after user approval
```
