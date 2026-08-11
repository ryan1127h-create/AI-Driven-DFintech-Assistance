# Role A Progress Log: Round 4

Date: 2026-08-11

Branch:

```text
backend_integration
```

Main branch status:

```text
No changes were pushed to main. Round 4 work stays on backend_integration.
```

## 1. Round 4 Scope

Round 4 connects Member B's newly uploaded business modules to the existing
FastAPI framework and fixes the missing test dependency.

Scope:

```text
1. Register Member B's API routers in app/api/v1/router.py.
2. Add pytest to requirements.txt so backend/tests can run in a fresh environment.
3. Verify compile, tests, and OpenAPI endpoint visibility.
```

## 2. Completed Changes

Completed items:

```text
1. Mounted course_recommendation routes.
2. Mounted program_comparison routes.
3. Mounted career_planning routes.
4. Added pytest>=8.0.0 to backend/requirements.txt.
5. Verified all Member B endpoints are visible in OpenAPI.
6. Verified Member B's pure logic tests pass locally.
```

## 3. API Impact

Newly exposed endpoints:

```text
POST /api/v1/course-recommendations
GET  /api/v1/program-comparisons/options
POST /api/v1/program-comparisons
POST /api/v1/career-plans
```

Previously these modules had code under app/modules/, but the API endpoints
were not reachable because they were not included in the central v1 router.

## 4. Code Changes

### 4.1 backend/app/api/v1/router.py

Change:

```text
Added imports for:
- app.modules.course_recommendation.api
- app.modules.program_comparison.api
- app.modules.career_planning.api

Added include_router(...) calls for all three modules.
```

Reason:

```text
FastAPI only exposes module routes after their APIRouter is included in the
central route registry. Without this, the endpoints return 404 and do not
appear in Swagger/OpenAPI.
```

### 4.2 backend/requirements.txt

Change:

```text
Added pytest>=8.0.0.
```

Reason:

```text
Member B added backend/tests/, but pytest was not listed as an installable
dependency. A fresh backend environment could not run python -m pytest tests -q.
```

## 5. Database Impact

New database objects:

```text
None in Round 4.
```

Migration status:

```text
No database migration was executed in Round 4.
```

Important existing dependency:

```text
The completed_courses column migration from Round 3 is still required before
Profile-dependent recommendation/comparison flows are safe in a shared database.
```

Required SQL from Round 3:

```sql
alter table student.user_profiles
  add column if not exists completed_courses text[] default '{}'::text[];
```

## 6. Frontend Impact

Frontend can now discover and call these endpoints from Swagger/OpenAPI:

```text
POST /api/v1/course-recommendations
GET  /api/v1/program-comparisons/options
POST /api/v1/program-comparisons
POST /api/v1/career-plans
```

Recommended frontend sequence:

```text
1. Use GET /api/v1/program-comparisons/options to populate comparison choices.
2. Treat course/program/career responses as advisory recommendation output.
3. Do not assume completed_courses fully understands undergraduate course titles yet.
```

## 7. Verification

Verification performed:

```text
python -m compileall -q app
python -m pytest tests -q
GET /openapi.json through FastAPI TestClient
GET /api/v1/program-comparisons/options through FastAPI TestClient
```

Results:

```text
compileall: passed
pytest: 38 passed
OpenAPI: /api/v1/course-recommendations visible
OpenAPI: /api/v1/program-comparisons/options visible
OpenAPI: /api/v1/program-comparisons visible
OpenAPI: /api/v1/career-plans visible
OpenAPI: /api/v1/checklist still visible
GET /api/v1/program-comparisons/options: 200
```

Known test warning:

```text
FastAPI TestClient printed a StarletteDeprecationWarning about httpx.
This warning did not fail the tests.
```

## 8. Remaining Risks

### 8.1 Completed courses are still limited

Status:

```text
Known limitation.
```

Meaning:

```text
Member B's current course recommendation logic mainly recognizes NUS-style
course codes. Undergraduate course titles such as "Machine Learning" are
reported as unrecognized and do not yet contribute to skill-gap matching.
```

### 8.2 Profile database migration still matters

Status:

```text
Required before shared testing.
```

Meaning:

```text
Recommendation and comparison flows can read profile through profile/interface.py.
If the database does not have student.user_profiles.completed_courses yet,
Profile reads can fail.
```

## 9. Current Status

Current status:

```text
Member B business modules: uploaded
Framework route integration: completed in Round 4
Test dependency: added
Tests: passing locally
Main branch: untouched
backend_integration branch: ready for commit/push
```

