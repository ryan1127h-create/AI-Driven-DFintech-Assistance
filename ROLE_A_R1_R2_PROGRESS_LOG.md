# Role A Progress Log: Round 1 and Round 2

Date: 2026-08-11

Branch:

```text
backend_integration
```

Main branch status:

```text
No changes were pushed to main. All Role A work was done on backend_integration.
```

## 1. Background

Role A is responsible for the backend foundation and Profile module integration work.

Current Role A scope:

```text
1. Make the imported backend installable and runnable.
2. Verify core endpoints: /health, /chat, /profile/resume.
3. Extend the Profile module so profile data can be read and manually corrected.
4. Keep module boundaries clean: other modules should read Profile through profile/interface.py.
```

## 2. Round 1: Backend Environment and Smoke Test

Related commits:

```text
1422b36 Add backend integration source
734fc2f Prepare backend local environment
```

### 2.1 Completed Features

Round 1 completed the basic backend setup and runtime verification.

Completed items:

```text
1. Added the imported backend source folder into the backend_integration branch.
2. Created a local virtual environment for backend testing.
3. Installed backend dependencies from requirements.txt.
4. Added the missing python-multipart dependency required by FastAPI file upload.
5. Verified that the backend app can be imported successfully.
6. Verified that the FastAPI server can start locally.
7. Verified /api/v1/health.
8. Verified /api/v1/chat.
9. Verified /api/v1/profile/resume using a temporary DOCX resume.
```

### 2.2 Code Changes

#### backend/requirements.txt

Change:

```text
Added python-multipart>=0.0.9
```

Reason:

```text
The /api/v1/profile/resume endpoint uses FastAPI UploadFile and File(...).
FastAPI requires python-multipart for multipart/form-data uploads.
Without this dependency, importing app.main fails before the backend can start.
```

#### backend/.env.example

Change:

```text
Added a template for local environment variables.
```

Reason:

```text
The backend depends on several environment variables, including KIMI_API_KEY,
OPENAI_API_KEY, KNOWLEDGE_DATABASE_URL, CONVERSATION_DATABASE_URL, and
SESSION_STORE_BACKEND. The template was added to make local setup reproducible.
```

Note:

```text
Another remote commit later deleted backend/.env.example:
39b6101 Delete backend/.env.example

This was not part of Role A's Round 2 work. I rebased on top of that remote
change and did not restore the file, to avoid overwriting teammate changes.
```

### 2.3 Verification Performed

Commands/checks used:

```text
python -m pip check
python -m compileall -q app
python -c "from app.main import app; print('IMPORT_OK')"
uvicorn app.main:app --host 127.0.0.1 --port 8011
```

API checks:

```text
GET  /api/v1/health
GET  /docs
POST /api/v1/chat
POST /api/v1/profile/resume
```

Results:

```text
pip check: passed
compileall: passed
app import: passed
/api/v1/health: passed
/docs: passed
/api/v1/chat: passed
/api/v1/profile/resume: passed with a simple temporary DOCX resume
```

### 2.4 Issues Found in Round 1

The basic chain can run, but profile resume extraction is not robust enough for all real resumes.

Observed issue types:

```text
1. Kimi sometimes returns empty or non-JSON content.
   Example error:
   Expecting value: line 1 column 1 (char 0)

2. Kimi sometimes returns malformed JSON.
   Example error:
   Unterminated string starting at...

3. Extracted fields can exceed database varchar limits.
   Example error:
   value too long for type character varying(50)
```

Meaning:

```text
/profile/resume works for simple text-based resumes, but it is fragile when
the model output is not strict JSON or when extracted field values exceed DB
schema limits.
```

Status:

```text
Not fixed in Round 1.
Recommended as a separate bugfix task.
```

Recommended future fix:

```text
1. Harden resume_agent.py JSON parsing.
2. Strip markdown JSON fences if present.
3. Return clearer errors when the model output is not valid JSON.
4. Normalize or validate extracted fields before writing to DB.
5. Avoid exposing raw internal exception strings directly to the frontend.
```

## 3. Round 2: Profile Read and Patch Endpoints

Related commit:

```text
7a1d328 Add profile read and patch endpoints
```

### 3.1 Completed Features

Round 2 extended the Profile module from upload-only to read/update capable.

Completed items:

```text
1. Added GET /api/v1/profile.
2. Added PATCH /api/v1/profile.
3. Added field-level profile patch logic.
4. Updated profile/interface.py so other modules can read and patch profile data through a public interface.
5. Added ProfilePatch request schema with validation.
6. Verified the new endpoints through FastAPI/OpenAPI and direct API calls.
```

### 3.2 New API Endpoints

#### GET /api/v1/profile

Purpose:

```text
Return the current placeholder user's stored profile.
```

Current behavior:

```text
Uses TEST_USER_ID because the backend does not have real authentication yet.
Returns 404 if no profile exists.
```

#### PATCH /api/v1/profile

Purpose:

```text
Allow the frontend/user to confirm or correct extracted profile fields without
uploading a new resume.
```

Current behavior:

```text
Only updates fields included in the PATCH request.
Omitted fields are preserved.
Returns 400 for an empty PATCH body.
Returns 422 for invalid field values or fields exceeding schema validation.
Returns 404 if no profile exists.
```

## 4. Round 2 Code Changes

### 4.1 backend/app/modules/profile/api.py

Changes:

```text
1. Added GET /profile endpoint.
2. Added PATCH /profile endpoint.
3. Connected both endpoints to profile service functions.
4. Preserved the existing POST /profile/resume endpoint.
```

Reason:

```text
The frontend needs to display the extracted profile after resume upload and
allow users to correct wrong or missing fields.
```

### 4.2 backend/app/modules/profile/service.py

Changes:

```text
1. Added get_profile().
2. Added patch_profile().
3. Kept generate_profile_from_resume() unchanged.
```

Reason:

```text
The service layer should orchestrate Profile module actions for the API layer.
API should not call repository directly.
```

### 4.3 backend/app/modules/profile/repository.py

Changes:

```text
1. Added patch(user_id, fields).
2. patch() updates only provided fields.
3. patch() returns None if the profile row does not exist.
```

Reason:

```text
Resume upload uses full overwrite semantics, but user correction should be
field-level patching. This prevents omitted fields from being cleared.
```

### 4.4 backend/app/modules/profile/interface.py

Changes:

```text
1. Added get_profile(user_id).
2. Added patch_profile(user_id, fields).
3. Updated __all__ to expose the public Profile module functions.
4. Preserved get_profile_summary_text() and get_lifecycle_stage().
```

Reason:

```text
Future modules such as course_recommendation, program_comparison, and
career_planning should access profile data only through profile/interface.py,
not by importing profile.repository directly.
```

This follows the backend architecture rule:

```text
Cross-module calls must go through the target module's interface.py.
```

### 4.5 backend/app/modules/profile/schemas.py

Changes:

```text
1. Added ProfilePatch schema.
2. Added enum-like Literal validation for lifecycle_stage, tech_level_std, and target_role_std.
3. Added length validation for fields backed by varchar columns.
4. Added numeric range validation for work_years, GMAT, GRE, TOEFL, IELTS, and intake_year.
5. Set extra="forbid" so unknown fields are rejected.
```

Reason:

```text
PATCH requests should fail early if the frontend sends invalid fields or values
that do not match the database schema.
```

## 5. Round 2 Verification

Verification performed:

```text
python -m compileall -q app
python -c "from app.main import app; print('IMPORT_OK')"
GET /api/v1/health
GET /api/v1/profile
PATCH /api/v1/profile
GET /openapi.json
```

Results:

```text
compileall: passed
app import: passed
/api/v1/health: passed
/api/v1/profile: passed
/api/v1/profile PATCH: passed
OpenAPI: GET/PATCH /api/v1/profile visible
Empty PATCH body: 400
Too-long school_tier: 422
```

Test cleanup:

```text
Temporary uvicorn logs were deleted.
__pycache__ folders were deleted.
The temporary test server on port 8012 was stopped.
```

## 6. Known Issues After Round 2

### 6.1 Resume extraction is still fragile

This is still unresolved:

```text
POST /api/v1/profile/resume may fail if Kimi does not return strict JSON.
```

Examples already observed:

```text
Expecting value: line 1 column 1 (char 0)
Unterminated string starting at...
```

Recommended next fix:

```text
Improve backend/app/modules/profile/agents/resume_agent.py.
```

### 6.2 Extracted values can still exceed DB column length

This is still unresolved for resume upload:

```text
value too long for type character varying(50)
```

Round 2 added validation for manual PATCH requests, but resume extraction still
needs normalization before repository.upsert().

Recommended next fix:

```text
Add extracted-field normalization before profile repository upsert.
```

### 6.3 TEST_USER_ID is still used

Current limitation:

```text
The backend still uses TEST_USER_ID as a placeholder identity.
```

Impact:

```text
This is acceptable for sandbox/demo testing, but real multi-user support will
need per-request user identity.
```

## 7. Current Status

Current branch head:

```text
7a1d328 Add profile read and patch endpoints
```

Current status:

```text
Role A Round 1: completed
Role A Round 2: completed
Main branch: untouched
backend_integration branch: updated and pushed
```

Recommended next Role A task:

```text
Fix /profile/resume robustness:
1. Harden Kimi JSON parsing.
2. Normalize extracted profile fields before DB write.
3. Improve error messages returned to frontend.
```

