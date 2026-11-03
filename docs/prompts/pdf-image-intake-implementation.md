Implement Pramana's mandatory Round 3 PDF/image intake feature end to end. Work as a senior engineer accountable for a working, secure, demonstrable result. Deliver implementation and verification, not just a plan. Keep the scope narrow and the evidence honest.

1. Context and current baseline

- Workspace: C:\Users\Ishaan\OneDrive\Pramana. Follow its AGENTS.md and any applicable nested instructions. Submission deadline: 3 November 2026, 23:59 IST. Check the actual remaining time; reserve the final 90–120 minutes for integration, deployment verification and submission.
- At prompt preparation, the checkout was clean on main at 1dd8ae5, with origin https://github.com/ananyap-20/Pramana.git. Recheck before editing and preserve other work. The older plan's references to local master at 52a5869 are stale; do not reset or replace this checkout.
- Existing stack: React + TypeScript + Vite; FastAPI/Python >=3.12; uv and npm lockfiles. Preserve the deterministic engine, evidence validator, and human approval boundary.
- Current input is pasted text or ordinary-paragraph DOCX. POST /api/reviews/analyze-document extracts and immediately analyzes DOCX; the frontend upload control also accepts only DOCX. Existing limits: 5 MiB upload, 20 MiB expanded DOCX, 200 ZIP entries, 100,000 extracted characters. Preserve valid existing behavior.
- No PDF/OCR dependencies, authentication, durable history, or durable job infrastructure are implemented in this inspected checkout. Tesseract was not found on PATH. Earlier in this chat the frontend build passed and lint returned two existing React-effect warnings; a backend pytest run stalled and was stopped. The README's historical 54 passing tests are not a fresh baseline. CI was discussed, not established.
- The Round 2 frontend at https://20ananyapandey.vercel.app/ loaded in this chat; its backend host and end-to-end behavior remain unverified. MongoDB Atlas and private storage are planned, not confirmed provisioned. The user intends to buy a domain; purchase and DNS setup are unconfirmed. Cloudflare DNS-only is the discussed Vercel frontend arrangement. Do not change accounts, DNS, billing, or deployment as part of local implementation without authorization.

2. Inspect first, then implement

Read C:\Users\Ishaan\OneDrive\Pramana\docs\backend-v1-plan-2026-11-02.md, especially sections 5 and 12. Inspect the actual code rather than trusting its older status notes. Start with:

- C:\Users\Ishaan\OneDrive\Pramana\backend\app\services\document_intake.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\main.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\schemas.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\domain.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\services\review_service.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\services\finding_validator.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\app\repositories\demo_repository.py
- C:\Users\Ishaan\OneDrive\Pramana\backend\tests
- C:\Users\Ishaan\OneDrive\Pramana\frontend\src\api\client.ts
- C:\Users\Ishaan\OneDrive\Pramana\frontend\src\pages\DraftWorkspacePage.tsx

Inspect dependency locks, receipt/review pages, configuration, and deployment files too. Run relevant existing checks with a bounded timeout and record failures before changes. Briefly state the implementation sequence and acceptance criteria, then proceed. Ask only when a consequential ambiguity or prerequisite needs a user decision; continue independent work meanwhile.

3. Required working journey

- Support text PDFs, scanned/mixed PDFs, and PNG/JPEG OCR, English-first. Keep pasted-text and DOCX flows working. Publish explicit supported layout/language limits; do not promise universal document understanding.
- Extract usable PDF text directly; OCR only pages/regions that need it. Preserve page order and avoid duplicated text from OCR plus an existing text layer. Declare handling of rotation, columns, tables and damaged text layers; never silently omit content or truncate to fit limits.
- Use the smallest suitable maintained toolchain. The plan names pypdfium2 and local Tesseract as candidates, not installed or mandatory choices. Check current official documentation, licenses, platform support and a real fixture before selecting and locking dependencies. Include the actual OCR executable and language-data setup for local Windows and the intended backend runtime.
- Provide a usable frontend flow: select/upload -> processing -> extraction preview -> correct/confirm uncertain text -> analyze -> evidence receipts -> human review. Show page/region context, extraction warnings, limits, and actionable errors using existing styling. Confirmation of transcription is separate from approval of content.
- Model the necessary states explicitly, such as queued, processing, needs_confirmation, ready, failed and expired. Do not display invented progress. Missing OCR runtime or parser failure must produce a clear failure, never a successful empty extraction or a clean-analysis result.
- Uncertain extraction must require explicit human confirmation. Requiring confirmation for all OCR is an acceptable conservative first policy. Missing confidence remains uncertain; an OCR score is not factual correctness or a calibrated probability.

4. Evidence integrity and confirmation

- Preserve the original file digest and immutable extracted-text versions. Carry file type, page/region references, coordinate convention where available, extraction method/tool version and relevant settings. Retain original bytes only within an explicit protected lifetime; a digest alone cannot support later original-file replay.
- Server-side confirmation must bind to the exact extraction ID, version/digest and authorized requester. Reject stale, tampered, expired or mismatched submissions. Never trust a client-supplied ready flag. Record confirmation time and the real actor if identity exists; never fabricate authenticated identity.
- Human correction creates a new immutable text version. Invalidate prior analysis/approval for changed text; distinguish human-edited text from verbatim extraction. Do not retain original-file coordinates for edited text unless they remain valid.
- Pass the exact accepted text through the existing deterministic review service and validator. Flagged quotes must match that evaluated version exactly. Preserve offset correctness across Python and TypeScript, including Unicode. Uploaded drafts do not automatically become approved brand evidence. Citation presence alone does not prove a finding correct.
- Use only Supported, Contradicted, Unsupported (needs verification), and Indeterminate (needs verification) as evidence statuses. Keep extraction workflow states separate. Preserve the missing-disclaimer exception: absent text has no fabricated quote/location. Never auto-publish, silently rewrite drafts, bypass validation, or equate Unsupported with false.

5. Safety, performance and missing prerequisites

- Treat files and embedded instructions as untrusted data. Validate supported extension, declared type, actual signature and parser result. Reject unsupported, encrypted/password-protected, empty and malformed inputs with safe errors. Do not execute macros/scripts, follow document instructions, fetch embedded URLs or send drafts to external AI/OCR services.
- Enforce configurable byte, expanded-size, page, decoded-pixel, render-resolution, text-length, concurrency and runtime limits before expensive work where possible. Bound uploads and parser output; sanitize filenames, prevent path traversal and clean temporary files on success, failure, timeout and cancellation.
- Run CPU-heavy parsing/rendering/OCR outside the API event loop in a controlled process/worker. Timeouts must terminate work, not merely stop awaiting it. Enforce applicable resource/filesystem/network restrictions in the supported runtime; a plain thread or background task is not a security sandbox or durable queue. Keep health/read requests responsive and reject excess work predictably.
- Reuse existing auth, repositories, storage and job infrastructure if they have since been added. Otherwise, identify those missing shared production foundations as release blockers. Complete independent local functionality without inventing a parallel auth/database/queue system. Any temporary development state must be bounded, expire, and be described honestly; process memory and local files are not durable or tenant-safe production infrastructure.
- Do not expose private files, drafts or extracted text through shared history, logs, public URLs or public caches. Use real ownership checks where available; never invent an organization from an untrusted request field. Do not claim private production readiness while access control/retention prerequisites remain unmet.
- Measure upload/acknowledgement, extraction/OCR and analysis separately. Do not apply millisecond API targets to full OCR completion or invent performance improvements.

6. Keep the code disciplined

- Make small, reversible changes with clear boundaries between validation, extraction/OCR, confirmation, rule execution and API serialization. Extend existing conventions; avoid unrelated refactors or a UI redesign.
- Add only dependencies, modules and configuration used by this feature. No speculative frameworks, generic plugin systems, duplicate pipelines, unused adapters, fake OCR, placeholder success paths or redundant comments. Explain only non-obvious invariants and security decisions.
- Preserve compatible existing endpoints and response behavior; introduce explicit schemas for new workflow stages. Do not turn this task into visual brand checks, analytics, competitor research, LLM advice or a broad infrastructure rewrite.
- Work on an appropriate codex/ branch when possible; preserve the user's work. Keep coherent, reviewable milestones. Follow AGENTS.md for commits, pushes, paid services and externally visible actions; prepare local work without stopping repeatedly for routine implementation decisions.

7. Verification and completion gates

- Test genuine text PDFs, scans, mixed PDFs and PNG/JPEG through the real installed tools, not only mocks. Use fictional fixtures with independent expected text. Keep some fixtures separate from tuning; measure paragraph recovery/order/omissions for supported text PDFs. The plan's >=95% paragraph-recovery target must be measured, not asserted. Report OCR text quality separately from rule-engine accuracy.
- Cover low/missing OCR confidence, confirmation and corrections, stale/tampered versions, expired inputs, requester isolation where implemented, duplicate submissions, bad signatures, malformed/encrypted/empty files, all resource limits, missing OCR binaries, timeouts and cleanup. Assert that the new document workflow cannot analyze uncertain extraction before confirmation. Include Unicode quote/span checks and existing DOCX/text/receipt/decision regressions.
- Run backend pytest and Python compilation, plus frontend production build and lint using the repository's lockfiles and environment. Investigate hangs/failures rather than copying historical results. Mock failure modes when useful, but retain a real OCR integration path in the documented test setup; skipped OCR tests do not establish OCR support.
- Verify the complete browser journey with a text PDF, a scanned PDF and an image, including uncertainty -> correction -> confirmation -> analysis and safe failure. Verify deployment packaging and health behavior with OCR installed. If deployed verification is unavailable, distinguish local verification from the remaining hosted release gate.
- Update setup/API documentation, supported limits, runtime requirements and the test matrix. Finish with changed files, exact commands/results, real-tool/browser evidence, measured timings/quality, remaining blockers, and a short reproducible judge demo. Do not label mocks, volatile state, untested deployment or unimplemented prerequisites complete.

Start with inspection and the first verifiable implementation milestone. Optimize for a complete, reproducible supported journey and defensible engineering evidence—the basis of a strong final-round demonstration.
