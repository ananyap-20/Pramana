# Editorial frontend integration — 3 November 2026

## Backend and working-tree reconciliation

Implementation began on `codex/pdf-image-intake` at `80d07b3ce1afed5f35605ed2218d91790625a955`. Local `main` and `origin/main` were at `1dd8ae5`; `master` was older at `52a5869`. A read-only `git ls-remote --heads origin` confirmed the remote intake branch still points to `80d07b3` and remote main to `1dd8ae5`. No newer backend branch was found. No fetch, pull, merge, checkout, commit, push or deployment was performed.

Pre-existing backend/configuration work adds optional private original-file retention and stricter deployment readiness. It was inspected and preserved. Other work staged backend/storage documentation changes during this task; those changes were also left intact. This task changes frontend code and frontend documentation only.

## Reference inspection

The supplied folder is actually `front end reference/stitch_pramana_brand_review_ui_redesign/`; there is no `frontend-reference/` directory in this checkout.

| Reference | Usable material | Adaptation |
|---|---|---|
| `warm_editorial_studio/DESIGN.md` | Warm paper, charcoal, gold, serif headings, restrained panels, responsive spacing | Shared CSS tokens and components |
| `landing_page/code.html` and screenshot | Header, manuscript studio, findings, rule footer | React studio using the real review APIs |
| `audit_policies/code.html` and screenshot | Policy cards, source/version details, navigation | Current active rules from the configuration API |
| `audit_trail/code.html` and screenshot | Metric strip, ledger, filters, inspection pane | Real metadata and organization snapshots/analytics |
| `pramana_minimal_reviewer_sign_in_sign_up/code.html` and screenshot | Focused reviewer gateway form | Existing administrator-issued organization-key authentication |

The reference is static HTML with Tailwind CDN configuration, inline JavaScript and Google Fonts/Material Symbols links. There is no React application, package manifest, install script, reusable component package or ZIP in the supplied folder. Local assets are four PNG screenshots and the design document. Inline scripts were inspected as text, never executed. No dependencies were installed or changed.

The reference includes fixed example audit records, fabricated latency/approval/remediation totals, simulated receipts and hashes, one-click draft rewrites, auto-unlocking approval, zero-retention/immutable-log claims, sharing, certificates, custom policy editing, SSO, passwords, self-service access requests and hardware-key sign-in. These are not live backend capabilities and were not copied as working features. Its warranty/logistics/FTC rules also differ from this backend's fictional terminology, prohibited phrase, plan fact and disclaimer checks.

The landing screenshot has an empty central canvas and policy screenshots include an overlapping tour. The HTML provides useful structure, but missing states needed implementation: real request progress, empty/error/retry states, PDF/image correction and confirmation, evidence provenance, role-sensitive decisions, unavailable visual configuration, actual pagination, and mobile navigation.

Typography uses local font stacks: Newsreader/Inter when present, Georgia/Segoe UI/system fallbacks otherwise. No remote font requests or CDN scripts were added. Icons are small local SVG components. The favicon now uses the Pramana mark.

## Interface and API integration

| Workflow | Actual contract |
|---|---|
| API status | `GET /health`, retry and honest availability state |
| Active policies | `GET /api/demo/config/lumadesk`; real rule/source versions |
| Text/DOCX | Existing `/api/reviews/analyze`, `analyze-document`, or authenticated `/api/audit/reviews/…` equivalents |
| PDF/image | Existing `/api/intake` capability-token upload, polling, previews, confirmation and version-pinned analysis |
| Evidence/human review | Existing evaluated response, Unicode-code-point spans, source excerpts, provenance and explicit attestation |
| Human decisions | Existing temporary/shared decision endpoints or authenticated expected-revision/idempotency contract |
| Demo ledger | `GET /api/reviews/history/lumadesk`; metadata only, latest 100 |
| Organization ledger | Existing paginated history, encrypted snapshots and analytics |
| Reviewer access | `GET /api/audit/me` with administrator-issued bearer key; never falls back after access failure |
| Retained original | `GET /api/audit/reviews/{run}/original`; optional storage failures remain visible |
| Static visual checks | `POST /api/visual/analyze`; types mirror `backend/app/visual_models.py` |

All original hash routes remain available. Added routes are `#/visual-checks`, `#/reviewer-access` and `#/guide`. Unknown routes show a recovery link. Navigation includes a skip link, current-page semantics, keyboard focus on route changes and visible focus indicators. Responsive CSS collapses the studio, policies, analytics and ledger inspector at smaller widths; the ledger scrolls within its own container.

Draft Studio restores the active evaluated run when returning from review. Editing clears that active result before re-analysis. Existing transcription edits, confirmation, provenance, expiration and exact-version analysis behavior remain connected through the original intake component. Suggestions do not alter the manuscript. Approval requires a human action and never publishes content.

Ledger search and decision filters apply only to loaded records and say so. Organization analytics retain their server-defined cohort/period and independent all-date history. Shared demo totals describe only the returned records. Inspection shows real decision events and, where authenticated, the saved exact draft; it does not invent campaign names, reviewer notes, redlines or proof seals.

Visual HTML remains plain textarea input and is sent as inert strings; it is never inserted into the DOM. Assets use `asset:asset_1` etc., with bounded PNG/JPEG input. The client checks the UTF-8 request size; the backend remains authoritative for schema, file validity, manifest approval and resource limits. Visual results do not alter or approve a review and are not stored in audit analytics.

## Setup and checks

Existing Node/Python dependencies and production configuration are unchanged. From `frontend/`:

```powershell
npm.cmd run test
npm.cmd run build
npm.cmd run lint
```

The new tests use Node's built-in test runner and TypeScript stripping; Node 24.18.0 was used here. They do not install packages or load private environment files. Node reports an experimental warning for its TypeScript-stripping API.

For the usual local app, follow the existing README startup commands and set `VITE_API_BASE_URL` to your actual backend. If using another frontend port, include its exact origin in backend `CORS_ORIGINS`. Connect organization access before analysis to use protected audit retention; private storage and visual manifests remain operator configuration.

## Actual verification

| Check | Result |
|---|---|
| Frontend contract/evidence regressions | 9 passed; real client code with explicitly mocked HTTP responses |
| TypeScript and Vite production build | Passed |
| Lint | Passed with no warnings |
| Full existing backend suite with `REQUIRE_REAL_OCR=1` | 183 passed, 11 skipped, 1 existing Starlette/httpx deprecation warning |
| Real local frontend-client → FastAPI journey | Passed for text, DOCX, human decisions/history, PDF extraction/preview, rejected pre-confirmation analysis, corrected confirmation version and provenance, confirmed analysis and document decision |
| Local CORS preflight | Passed for exact test frontend origin |
| Missing visual manifest | Real endpoint returned 404, preserved as an error |
| Git whitespace review | Passed |
| Remote branch freshness | Confirmed with read-only remote branch-tip lookup |

The live check used fictional generated PDF/DOCX and text fixtures, a loopback-only in-memory API on port 8011, local OCR tooling and a frontend on port 5178. It used the Vite-transformed frontend API client, not just independently invented HTTP requests. No real organization's drafts or secrets were used.

All 11 skipped backend tests require a disposable local MongoDB; database/container restart, backup/restore, durable audit snapshots and private original retention were therefore not freshly verified end to end. Docker was unavailable on PATH. No Atlas/Bunny requests or external storage writes were made by this frontend task.

Browser screenshots and interactive/responsive journeys remain **unverified**. The browser host was unavailable. The native browser restored an unrelated signed-in Render page; automatic approval review rejected taking a screenshot of that private page, and later native interaction detected user input. No private dashboard screenshot was taken. A separate in-app local-tab attempt also failed because the browser host was unavailable. Live API checks are not a substitute for browser verification.

Before release, visually check desktop/tablet/mobile layouts, keyboard navigation and screen-reader announcements; exercise analysis → receipts → decision → history, DOCX and confirmed PDF/image flows, policy retry/API-down states, visual success with an approved test manifest, and reader/reviewer organization journeys with a disposable database.

## Remaining unavailable or conditional features

- Fictional LumaDesk sample text is visibly labeled; returned findings, history and totals use backend data.
- Organization audit needs configured MongoDB, encryption and administrator-issued access. Private original downloads additionally need configured retained-file storage and a retained original for that run.
- Static visual checks need an active approved manifest. Rendered-page analysis and full accessibility certification are unavailable.
- No SSO, signup, password recovery, hardware-key login, custom-policy editor, sharing/publishing service, cryptographic compliance seal or simulated analytics is presented as live functionality.
