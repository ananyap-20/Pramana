# Three mandatory features: local acceptance

3 November 2026. This report supersedes earlier declaration-only visual checks and skipped real-database/browser acceptance notes. The application remains account-free; human review and approval are separate explicit actions. Nothing was pushed or deployed.

## What was completed

| Promise | Implemented and exercised |
|---|---|
| PDF/image intake | Real text PDF, scanned/mixed PDF and PNG/JPEG OCR; previews; correction and immutable confirmation; exact evaluated text/quote spans; provenance; explicit human decision; safe failures and limits. |
| Visual brand/accessibility | Real isolated Chromium rendering; inherited/cascaded colors, responsive viewport, computed contrast/font metrics and geometry; exact approved sample-logo bytes; configured palette and alt checks; explicit uncertainty for unresolved effects. The static mode remains compatible. |
| Persistent audit/analytics | Real MongoDB snapshots and decisions; app/database restart; concurrency and idempotency; source-event/analytics reconciliation; retention; real mongodump/mongorestore into a separate test database. |

The Visual Checks tab now has a fictional LumaDesk sample and actual rendered/static and desktop/mobile controls. The sample policy and PNG are explicitly fictional and never substitute for the missing supplied Pramana logo. Real brands require verified operator-owned policies/assets. Original-file download controls appear only when storage is configured. Closing the initial walkthrough now returns keyboard focus to the main workspace.

## Verification results

- **241 backend/acceptance tests passed, zero failed, zero skipped**. Includes 23 real-renderer cases, 14 real-MongoDB cases, and 8 production-frontend browser journeys.
- **13 frontend tests passed**; lint, TypeScript/production build and Python compilation passed.
- All six independent PDF/OCR fixtures passed the recovery and exact quote-span gates.
- Final runner exit code: 0. Evidence timestamp: `2026-11-03T17:38:57.567157+00:00`.
- Backend emitted 23 dependency deprecation warnings; Node emitted its existing experimental TypeScript-stripping warning. No application failure was suppressed.

The PDF/OCR corpus recovered 18/18 expected paragraphs in order across three held-out two-page text PDFs, plus 9/9 across the scanned PDF/PNG/JPEG fixtures. The held-out PDF gate enforces at least 95% recovery. Similarity/normalization metrics are not used to fabricate original quotes; evaluated drafts and each quoted span are also checked exactly. These six supported fixtures do not establish arbitrary-document OCR accuracy.

The production-frontend browser journeys test fresh no-account entry, Retry, reduced motion, focus restoration, mobile overflow across all tabs, Unicode text and DOCX, PDF/PNG/JPEG preview-edit-confirm-analyze, explicit decisions, reopening saved evidence and downloading the exact original after an API restart. Rendered visual fixtures include near-threshold normal/large text, transparency, gradients/effects uncertainty, source/input hashes, malicious input, exact logo/alt and hard deadlines.

Native MongoDB is bound only to loopback with a disposable test directory/namespace. Original-file browser tests use actual encrypted disk objects through a test-only local transport. This tests the storage contract across restart, not Bunny's live service. Historical private collections are preserved separately from the new shared public workspace.

## Reproduce the complete gate on this Windows workspace

```powershell
uv sync --locked --all-groups
uv run playwright install chromium
uv run python scripts/verify_mandatory.py --mongod tmp/mongodb-runtime/mongod.exe --mongo-tools tmp/mongodb-runtime --browser-path tmp/browser-runtime --tesseract tmp/ocr-runtime/tesseract/tesseract.exe --tessdata tmp/ocr-runtime/tesseract/tessdata
```

The MongoDB server, backup tools, OCR and browser runtimes are local ignored test tools, not committed binaries. The native MongoDB server package was checked against MongoDB's published SHA-256; database tools came from the official HTTPS download and their measured SHA-256 is recorded in the execution evidence. Install matching official tools or pass their own paths on another machine. A default browser installation can omit `--browser-path`.

The runner builds the actual frontend with a same-origin API base, runs lint and frontend tests, starts a disposable real database, runs the entire backend/browser/renderer suite, rejects skipped tests, measures the independent extraction corpus, and compiles Python. It never loads private .env files or uses a live cloud database. Machine-readable evidence is `tmp/mandatory-verification/results.json`; JUnit is beside it. A portable copy of the result is in `docs/mandatory-feature-verification.json`. Browser screenshots are under `tmp/acceptance-screenshots`.

## Setup and remaining operational boundaries

Use [README](../README.md), [visual setup](visual-checks.md), [intake setup](pdf-image-intake.md), and [audit configuration](audit-and-analytics.md). Retained audit requires MongoDB plus preserved encryption keys; load .env and .env.audit together and require `/ready` to report `audit: true`. Missing optional configuration must not be mistaken for durable storage. No account/provider configuration is needed.

All three promises are verified within the documented supported local scope. This is not a claim of production privacy, complete WCAG compliance, handwriting/complex-layout OCR accuracy, approximate/flattened-logo recognition, or general browser exploit resistance. These are explicit scope limits, not silent passes. Gradients, overlays and unsupported effects stay Indeterminate and require review.

A live host, the Linux/container build and real Bunny provider were not changed or tested. Deploying the current source, installing its Chromium/OCR runtime, and verifying the hosted journey remain separately authorized operational work. No cloud costs or configuration were changed. Existing dependency deprecation/experimental warnings are recorded; no application test failure is hidden by them.

## Principal files changed in this continuation

- Renderer/API: `backend/app/services/rendered_visual.py`, `rendered_visual_worker.py`, `visual_process.py`, `intake_process.py`, `backend/app/visual_models.py`, `visual_api.py`, `repositories/visual_manifest.py`, and `backend/app/data/lumadesk-visual-demo.json` / `lumadesk-demo.png`.
- Real acceptance: `backend/tests/local_mongo.py`, `browser_server.py`, `test_browser_workflows.py`, `test_rendered_visual.py`, `conftest.py`, `test_audit.py`, `scripts/verify_mandatory.py`, and `scripts/verify_intake.py`.
- Frontend: `frontend/src/api/client.ts`, `pages/VisualChecksPage.tsx`, `pages/HumanReviewPage.tsx`, `components/Walkthrough.tsx`, and `components/DocumentProvenance.tsx`.
- Setup/evidence: `pyproject.toml`, `uv.lock`, `Dockerfile`, `.env.example`, `README.md`, and the current visual/audit/roadmap/verification documents. Pre-existing unrelated worktree changes were preserved.
