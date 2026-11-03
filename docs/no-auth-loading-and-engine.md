# No-account entry, loading and engine change report

Historical report for the first change. Its outstanding browser/real-database checks are superseded by [the subsequent three-feature acceptance report](mandatory-feature-verification.md).

Local source changes only, 3 November 2026. No push, deployment, private environment-file edits, cloud changes or external AI analysis were performed.

## Result

The React application and FastAPI routes require no identity, provider, session, CSRF exchange or user access key. Removed the sign-in/sign-up/reset/provider UI, account controls, profile route, Firebase clients/server verification and dedicated dependencies. Existing per-file extraction capabilities remain; these protect possession of an individual upload and are not accounts.

The first HTML paint and React initialization display Pramana, a warm welcome and the existing proportional P mark. No separate supplied logo was found among the repository assets; `frontend/public/favicon.svg` is the temporary existing-brand fallback. API readiness has a 12-second timeout and Retry. Module download failure/stall also exposes Retry. The welcome fades for 220 ms (zero under reduced motion), unmounts before the studio mounts, and the existing Shell focuses main content. Real animation, keyboard and screen-reader behavior were not manually verified because browser automation was unavailable.

Text/DOCX metadata mode remains functional without MongoDB. Optional encrypted retained audit uses new shared records in `public_reviews_v1` / `public_files_v1`; visitors share those records and anonymous human decisions. Previous account/organization collections remain separate and inaccessible from public review routes. Historical original expiry cleanup remains enabled. Public destructive administration/profile routes were removed; deletion remains an operator repository operation. Review approval remains a separate explicit human action.

DOCX now reuses the existing disposable extraction worker (deadline, memory, temporary-output and platform process limits). Filename, MIME, archive/macros/embedded payloads, malformed XML, expanded size and extracted text checks return safe errors. Public text bodies are bounded before parsing; invalid text errors do not echo draft content. PDF/image limits, per-page provenance, low-confidence OCR warnings, confirmation and immutable versions are preserved. Comparison does not replace original evaluated text or offsets.

Finding validation checks brand, allowed state, exact nonempty quote/span, approved rule/source version and excerpt, and deterministic applicability independently of candidate output. Deduplication keeps distinct locations/evidence. No heuristic, extraction result or evidence status records a human decision.

The established compact, less-boxy studio styles and responsive rules are preserved. Audit history supports metadata mode as well as configured retained analytics. Human Review no longer requests an account profile.

## Checks actually run

- `.venv/Scripts/python.exe -m pytest`: 199 passed, 11 skipped, 23 dependency deprecation warnings. The real default middleware ran; the obsolete identity-bypass fixture was removed.
- `.venv/Scripts/python.exe -m pytest backend/tests/test_no_auth.py backend/tests/test_api.py backend/tests/test_document_intake.py backend/tests/test_finding_validator.py`: 43 passed before the final independent-applicability test; a later Unicode/no-account subset also passed 21 tests.
- `.venv/Scripts/python.exe -m compileall -q backend scripts`: passed.
- `npm.cmd test` in frontend: 13 passed. Covers public/retained API selection, exact Unicode drafts, explicit decisions/revisions, tab storage, old-private-state exclusion, extraction capabilities, visible errors, initial accessible welcome markup, and module-load retry handling.
- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed, including TypeScript and production Vite build.
- `git diff --check`: passed (Git emits an LF/CRLF informational warning for uv.lock).
- `uv lock` and `npm.cmd install --package-lock-only --ignore-scripts`: succeeded; Firebase and its unused transitive dependencies were removed. The existing installation supplied the test runtime; no live credentials were loaded.

Windows initially blocked the uv cache/runtime/native modules inside the sandbox. Authorized local execution access allowed the Python checks. Offline lock resolution lacked cached packages; normal package-registry lock resolution succeeded.

## Limits and unverified behavior

Computer Use ended before opening the local app because it could not identify the current Windows browser URL confidently enough to enforce policy. No manual visual, responsive, keyboard-focus, reduced-motion or screen-reader journey is claimed. Welcome markup and pre-React retry handling have automated coverage; the complete browser handoff remains unverified.

Real MongoDB/container acceptance tests are skipped without the existing explicit disposable test settings. Mocked MongoDB verifies shared snapshots, decisions, restart/reopen and preservation of prior private partitions; this does not establish real database durability. No hosted app, Bunny transport, production sandbox/privacy, recovery or general OCR accuracy was verified. Existing backend deprecation warnings and Node's experimental TypeScript-stripping warning remain.

## Exact files changed by this task

Status: M modified, D removed, A created.

```text
M	.env.example
M	README.md
M	backend/app/audit_api.py
M	backend/app/audit_middleware.py
D	backend/app/identity_api.py
M	backend/app/intake_api.py
M	backend/app/main.py
M	backend/app/schemas.py
M	backend/app/services/audit_security.py
M	backend/app/services/document_intake.py
M	backend/app/services/extraction_store.py
M	backend/app/services/finding_validator.py
D	backend/app/services/identity.py
M	backend/app/services/intake_process.py
M	backend/app/services/intake_worker.py
M	backend/app/services/review_service.py
M	backend/app/services/rule_engine.py
M	backend/tests/conftest.py
M	backend/tests/test_audit.py
M	backend/tests/test_document_intake.py
M	backend/tests/test_finding_validator.py
D	backend/tests/test_identity.py
D	backend/tests/test_identity_intake.py
M	docs/audit-and-analytics.md
D	docs/authentication.md
M	docs/pdf-image-intake.md
M	docs/storage-deployment.md
M	frontend/.env.example
M	frontend/index.html
M	frontend/package-lock.json
M	frontend/package.json
M	frontend/src/App.tsx
M	frontend/src/api/client.ts
D	frontend/src/auth/AuthGate.tsx
D	frontend/src/auth/firebase.ts
D	frontend/src/components/AuditAccess.tsx
M	frontend/src/components/DocumentProvenance.tsx
M	frontend/src/components/ReviewLedger.tsx
M	frontend/src/components/TopBar.tsx
M	frontend/src/index.css
M	frontend/src/pages/AuditDashboard.tsx
M	frontend/src/pages/HumanReviewPage.tsx
M	frontend/tests/api-client.test.mjs
D	frontend/tests/auth.test.mjs
M	pyproject.toml
M	render.storage.yaml
M	scripts/check_audit_deployment.py
M	scripts/create_audit_credentials.py
M	scripts/export_render_settings.py
M	uv.lock
A	backend/tests/test_no_auth.py
A	frontend/src/components/WelcomeTransition.tsx
A	frontend/tests/welcome.test.mjs
A	docs/no-auth-loading-and-engine.md
```

The supplied `pramana_no_auth_loading_and_engine.md` remains untracked and unchanged. A separate deletion of `docs/prompts/pdf-image-intake-implementation.md` appeared in the worktree during execution; this task did not create or restore that unrelated change.
