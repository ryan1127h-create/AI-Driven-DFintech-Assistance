"""
Business modules — one isolated package per business domain (chatbot,
profile, and whatever comes next). Modules don't import each other's
internals; the only exception is a module's own `interface.py`, if it has
one, which is the single file other modules are allowed to import from (see
app/modules/profile/interface.py). Anything genuinely shared across every
module (DB/Redis/LLM clients, RAG retrieval) stays outside app/modules/, in
app/clients/, app/repositories/, app/services/.

Standard internal layout for a module (see app/modules/chatbot/,
app/modules/profile/ for reference — not every file is required, e.g. a
module with no LLM calls has no agents/, one with nothing to expose
cross-module has no interface.py):

  api.py          FastAPI router — the module's HTTP layer
  schemas.py      HTTP request/response models
  interface.py    (optional) the only file other modules may import from
  service.py      orchestration / use-case entry point(s)
  agents/         (optional) LLM-agent logic, if this module calls an LLM
  models.py       domain dataclasses
  repository.py   data access for this module's own tables
  schema/         SQL DDL for this module's own tables
"""
