# Role A Progress Log: Round 3

Date: 2026-08-11

Branch:

```text
backend_integration
```

Main branch status:

```text
No changes were pushed to main. All Round 3 work stays on backend_integration.
```

## 1. Round 3 Scope

Round 3 focuses on API contract alignment only.

Requested direction:

```text
1. Add checklist interfaces that follow the current backend module structure.
2. Add completed_courses to Profile so course/program recommendation can use prior coursework later.
3. Do not implement the full checklist business engine in this round.
4. Keep database and frontend impact clear for team coordination.
```

## 2. Completed Features

Completed items:

```text
1. Added completed_courses to Profile API models.
2. Added completed_courses to Profile repository field list.
3. Added completed_courses normalization for manual PATCH and resume extraction output.
4. Added completed_courses to the profile summary text exposed through profile/interface.py.
5. Added a database migration SQL file for student.user_profiles.completed_courses.
6. Added a new checklist module under app/modules/checklist/.
7. Added GET /api/v1/checklist.
8. Added PATCH /api/v1/checklist/items/{item_id} as a future persistence contract.
9. Registered checklist routes in the central v1 router.
10. Verified the checklist endpoints appear in OpenAPI.
```

Important limitation:

```text
Checklist is contract-only in this round.
It does not read or persist real submitted document status yet.
PATCH /api/v1/checklist/items/{item_id} intentionally returns 501 Not Implemented.
```

## 3. New API Contract

### 3.1 GET /api/v1/checklist

Purpose:

```text
Expose the checklist response shape for frontend and future checklist-service integration.
```

Current behavior:

```text
Returns a stable contract-only checklist payload with implementation_status = "contract_only".
All checklist item statuses are "unknown".
No actual document submission state is read from the database yet.
```

Response shape:

```json
{
  "user_id": "string",
  "lifecycle_stage": "string|null",
  "implementation_status": "contract_only|partial|implemented",
  "items": [
    {
      "id": "string",
      "title": "string",
      "category": "profile|admission_document|test_score|reference|finance|other",
      "requirement": "required|conditional|recommended|optional",
      "status": "unknown|not_started|in_progress|completed|not_applicable",
      "owner": "string",
      "description": "string|null",
      "evidence_source": "string|null",
      "blocking_fields": ["string"]
    }
  ],
  "outstanding_required_count": 0,
  "notes": ["string"]
}
```

### 3.2 PATCH /api/v1/checklist/items/{item_id}

Purpose:

```text
Define the future endpoint for updating one checklist item's persisted status.
```

Request body:

```json
{
  "status": "unknown|not_started|in_progress|completed|not_applicable",
  "evidence_source": "string|null",
  "note": "string|null"
}
```

Current behavior:

```text
Returns 501 Not Implemented.
This is intentional because the checklist persistence/business logic is assigned to another teammate.
```

## 4. Completed Courses API Change

### 4.1 GET /api/v1/profile

New response field:

```json
{
  "completed_courses": ["Data Structures", "Corporate Finance"]
}
```

Purpose:

```text
This field represents applicant prior/relevant courses, including undergraduate courses.
It is for course recommendation and program recommendation personalization.
It is not used for MSc DFT credit-completion or graduation-progress tracking.
```

### 4.2 PATCH /api/v1/profile

New request field:

```json
{
  "completed_courses": ["Data Structures", "Machine Learning", "Corporate Finance"]
}
```

Validation behavior:

```text
1. Empty strings are removed.
2. Duplicate course names are removed case-insensitively.
3. Each item must be 120 characters or fewer.
4. The list can contain at most 50 items.
```

## 5. Code Changes

### 5.1 backend/app/modules/checklist/

New files:

```text
backend/app/modules/checklist/__init__.py
backend/app/modules/checklist/api.py
backend/app/modules/checklist/interface.py
backend/app/modules/checklist/schemas.py
backend/app/modules/checklist/service.py
```

Reason:

```text
The backend architecture expects each business module to own its API, schemas,
service, and public interface. Checklist is now isolated as its own module,
matching chatbot and profile structure.
```

### 5.2 backend/app/api/v1/router.py

Change:

```text
Registered checklist_api.router under /api/v1.
```

Reason:

```text
The central v1 router is the single place where business module routes are mounted.
```

### 5.3 backend/app/modules/profile/schemas.py

Change:

```text
Added completed_courses to ProfileOut and ProfilePatch.
Added validation for completed_courses.
```

Reason:

```text
Frontend can display and manually edit prior coursework for later recommendation modules.
```

### 5.4 backend/app/modules/profile/service.py

Change:

```text
Added completed_courses normalization before repository writes.
```

Reason:

```text
This reduces bad data before the future recommendation module reads Profile.
```

### 5.5 backend/app/modules/profile/interface.py

Change:

```text
Profile summary text now includes relevant prior/completed courses when present.
```

Reason:

```text
Future chatbot, course recommendation, and project recommendation modules should access
profile facts through profile/interface.py, not by importing profile repository directly.
```

### 5.6 backend/app/modules/profile/schema/

New migration:

```text
backend/app/modules/profile/schema/user_profiles_completed_courses.sql
```

Schema clone updated:

```text
backend/app/modules/profile/schema/student_schema_clone.sql
```

Reason:

```text
The database needs a column to store applicant prior coursework.
```

## 6. Database Impact

Database change required:

```sql
alter table student.user_profiles
  add column if not exists completed_courses text[] default '{}'::text[];
```

New table:

```text
No new table in Round 3.
```

Checklist database impact:

```text
No checklist table was added.
No checklist persistence was implemented.
The future functionality teammate can decide whether checklist state should live in
student.application_documents, a new checklist table, or a derived view.
```

Important warning:

```text
After this code is deployed, the database migration must be applied before using
GET/PATCH /api/v1/profile, because profile repository now selects completed_courses.
```

Migration execution status:

```text
Not executed by Codex in Round 3.
The SQL file is prepared for the database teammate to run.
```

## 7. Frontend Impact

Frontend changes needed:

```text
1. Profile page/form can add completed_courses as a string array field.
2. Frontend should send PATCH /api/v1/profile with completed_courses when users edit prior courses.
3. Checklist page can call GET /api/v1/checklist to inspect the response shape.
4. Checklist item updates should not be wired as a completed feature yet because PATCH currently returns 501.
```

Suggested frontend handling:

```text
If implementation_status is "contract_only", show checklist as unavailable/preview/internal only.
Do not present checklist completion status as real application progress yet.
```

## 8. Verification

Verification performed:

```text
python -m compileall -q backend/app
GET /openapi.json through FastAPI TestClient
GET /api/v1/checklist through FastAPI TestClient
PATCH /api/v1/checklist/items/cv through FastAPI TestClient
ProfilePatch completed_courses schema validation
```

Results:

```text
compileall: passed
OpenAPI: /api/v1/checklist visible
OpenAPI: /api/v1/checklist/items/{item_id} visible
GET /api/v1/checklist: 200
GET /api/v1/checklist: returned implementation_status = contract_only and 10 items
PATCH /api/v1/checklist/items/cv: 501 as intended
ProfilePatch completed_courses cleanup: passed
ProfilePatch too-long course item: 422 validation path confirmed
```

Known test warning:

```text
FastAPI TestClient printed a StarletteDeprecationWarning about httpx.
This is dependency-level noise and did not fail the test.
```

## 9. Known Issues After Round 3

### 9.1 Checklist is not functional yet

Status:

```text
Not implemented.
```

Meaning:

```text
The API contract exists, but real checklist status calculation/persistence still needs to be built.
```

### 9.2 Database migration is required for completed_courses

Status:

```text
Migration SQL prepared, not executed.
```

Meaning:

```text
The database teammate must run user_profiles_completed_courses.sql before Profile endpoints
can safely read/write completed_courses in a shared environment.
```

### 9.3 Resume extraction robustness is still unresolved

Status:

```text
Still unresolved from earlier rounds.
```

Meaning:

```text
POST /api/v1/profile/resume can still fail when the LLM returns malformed JSON
or invalid field values outside the expected schema.
```

## 10. Current Status

Current status:

```text
Role A Round 3: interface/API contract completed
Checklist feature engine: not implemented
Database migration file: prepared
Frontend contract: available through OpenAPI
Main branch: untouched
backend_integration branch: ready for commit/push
```

