# course_recommendation — database schema

This module is currently read-only: it consumes the shared knowledge base
(`app.document_chunks`, via `app/repositories/knowledge_repository.py`) and
owns no tables of its own.

If recommendation history ever needs persisting, add a
`student.course_recommendations` table here (per the integration plan §11)
and a matching write path in `repository.py`.
