# Contributing

Code standards and submission rules for this repo. Applies to everyone — code
written by hand or generated with AI tools is held to the same bar.

## Code standards

- **Layering in `backend/app/`**: `api > orchestrator > tools > domains >
  adapters > ports/core`. A higher layer may import a lower one, never the
  reverse. Domains only reach each other through `interface.py`, never another
  domain's `service.py`/`repository.py` directly. Verify with:
  ```
  cd backend && PYTHONUTF8=1 .venv/Scripts/lint-imports.exe --config app/.importlinter
  ```
- **`api.py` has no business logic** — parse the request, call `service.py`,
  shape the response. Cross-domain calls and validation belong in `service.py`.
- **Comments explain non-obvious *why***, never *what* (names should cover
  that), and never migration history ("moved from X", "phase N"). They describe
  current behavior only.
- **No premature abstraction** — three similar lines beat an early interface.
  Don't add config knobs, fallbacks, or generality for a need that doesn't
  exist yet.
- **No fabricated dependencies or APIs** — every import must be a real,
  already-used package/version. Don't add one you haven't verified exists.
- **No secrets in committed files** — the repo-root `.env` (gitignored) is the
  only place credentials live.

## Commit & PR rules

- Branch off `main`, one branch per change, short-lived. Never push directly
  to `main`.
- Commit format: `<type>(<scope>): <imperative summary>`, e.g.
  `fix(auth): reject expired tokens on refresh`. Types: `feat`, `fix`,
  `refactor`, `test`, `docs`, `chore`, `perf`.
- If a commit is substantially AI-generated (not just autocomplete), add a
  trailer: `Assisted-by: <tool>[:model]` — e.g. `Assisted-by: Claude
  Code:claude-sonnet-5`. Same convention used by the Linux kernel, Apache, and
  LLVM. The human author is still fully responsible for the code either way.
- PRs need at least one approval before merging. Keep PRs small and scoped to
  one change — split up large AI-generated diffs rather than submitting them
  as one PR nobody can meaningfully review.
- Before opening a PR:
  - [ ] `pytest backend/app/tests/` passes (if `backend/app/` changed)
  - [ ] `import-linter` passes, 2/2 contracts (if `backend/app/` changed)
  - [ ] `npm run build` passes (if `frontend/` changed)
  - [ ] You've read and understood every line of any AI-generated code in the
        diff — don't commit code you can't explain
  - [ ] The change was actually run and manually verified, not just unit-tested
