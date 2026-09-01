"""
Agent-backend, product-architecture build.

Layers, top to bottom (see .importlinter for the enforced dependency
direction): api -> orchestrator -> tools -> domains -> adapters -> ports/
core. Each layer may depend on anything below it, never above it.

  api/            HTTP surface — one FastAPI router per mounted domain.
  orchestrator/   The chatbot's own reasoning loop — the only component
                  that talks to the user. Calls tools, never a domain
                  directly.
  tools/          The Tool contract (name, input schema, handler, timeout,
                  fallback) every callable capability is exposed through,
                  plus the shared, domain-agnostic tools (retrieval,
                  summarization, ...) that aren't owned by any one domain.
  domains/        One bounded context per business capability (auth,
                  profile, course recommendation, ...). Each domain owns
                  its own data and workflow, and exposes itself to the
                  rest of the app only through its own interface.py.
  adapters/       Concrete implementations of the ports below, wired to
                  real infrastructure (Postgres, Redis, an LLM provider, ...).
  ports/          Abstract contracts for infrastructure a domain needs
                  (a relational store, a cache, ...), independent of any
                  specific vendor or driver.
  core/           Cross-cutting kernel visible to every layer — config,
                  logging, the shared error taxonomy, resilience helpers.
                  Contains no business logic of its own.
"""
