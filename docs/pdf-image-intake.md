# PDF/image intake: local implementation and verification

## 3 November follow-up: import/configuration fixes

The checked-in Render manifests now use the existing Docker runtime with Tesseract/English data and set `PRAMANA_ENABLE_LOCAL_INTAKE=1`. The setup example enables intake too; the application still honors an explicit `0` and defaults off when the variable is absent. Existing hosted services must apply these settings and redeploy; editing a manifest does not change a running service. No deployment was performed.

The current authenticated flow uses a verified session cookie plus CSRF protection, with the extraction capability also bound to the user. Confirmed analysis goes through `/api/audit/intake/{id}/analyze` and saves the accepted text and receipts to the workspace audit repository. The original anonymous endpoints documented below describe the earlier implementation and are blocked by the current outer identity middleware.

Verification: 16 existing PDF/image tests passed with real extraction/OCR. Three additional `test_identity_intake.py` acceptance cases exercised text-only, scanned and mixed PDFs through the actual identity/CSRF middleware, preview, confirmation, audit analysis and decision routes; cross-user access returned 404. Firebase verification and MongoDB were local test doubles; parsers and Tesseract were real. The full backend suite completed without failures; optional integration cases skipped when their external services were unavailable.

The earlier Windows hang happened before extraction, in Python's asyncio loopback socket creation under the restricted execution sandbox. Running the same tests with local socket/process access resolved it. Bounded upload handling remains in place. The frontend provides extraction/preview retries, releases preview URLs and prevents confirmation before every preview is available.

Browser verification on an isolated localhost server with fictional data: scanned PDF upload, OCR and rendered preview, explicit confirmation, analysis and a human revision decision passed. No live Firebase, Atlas or hosted OCR verification is implied.

Implemented 3 November 2026 on `codex/pdf-image-intake`, from `main` at `1dd8ae5`.
The pre-existing untracked `docs/prompts/` directory was preserved. Nothing was pushed or deployed.

## Supported journey

Upload PDF/PNG/JPEG → queued/processing → page preview and editable transcription → explicitly confirm transcription → analyze the accepted version → evidence receipts → human decision.

The existing pasted-text and ordinary-paragraph DOCX APIs remain compatible. The deterministic engine, validator, four evidence statuses, and missing-disclaimer exception are unchanged. A transcription confirmation is **not** content approval. Uploaded copy is never promoted to approved brand evidence.

Supported scope: upright English printed text, simple paragraphs. Text-only PDF pages use PDFium text extraction. Pages containing raster images or unusable text use whole-page OCR, replacing rather than appending the text layer. This conservative choice also OCRs decorative images. Page order and two-newline separators are explicit. PDF `/Rotate` is honored by rendering; image EXIF orientation is applied. Physical sideways text without metadata, skew, handwriting, complex columns, tables, math and damaged-but-plausible text layers need manual checking; layout reconstruction is not promised. Empty pages have warnings and previews; entirely unreadable documents fail. No silent truncation.

Every extraction requires confirmation. OCR scores are uncalibrated recognition signals; missing scores remain unknown. Edited pages lose original coordinates; unchanged pages retain geometry with recalculated text offsets. PDF direct-text geometry is page-level, not a claim of exact glyph bounds. OCR regions use pixel bounds after rendering/orientation. API offsets are Unicode code points, including in the TypeScript receipt display.

## Run on Windows

Install the [Windows Tesseract build linked by its maintainers](https://github.com/UB-Mannheim/tesseract/wiki), including `eng.traineddata`. This run installed 5.5.3.20260724 under the ignored `tmp/ocr-runtime/tesseract` directory. It is machine-local and is not committed.

```powershell
uv sync --locked --all-groups
$env:PRAMANA_ENABLE_LOCAL_INTAKE='1'
$env:TESSERACT_CMD=(Resolve-Path 'tmp/ocr-runtime/tesseract/tesseract.exe').Path
$env:TESSDATA_DIR=(Resolve-Path 'tmp/ocr-runtime/tesseract/tessdata').Path
& $env:TESSERACT_CMD --version
& $env:TESSERACT_CMD --list-langs
uv run --locked uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# Another terminal, from frontend/:
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

For a normal system installation use `C:/Program Files/Tesseract-OCR/tesseract.exe` and its `tessdata` directory instead. These settings can go in an ignored `.env` loaded with `--env-file .env`. Intake is disabled by default. Only fictional non-sensitive content is authorized for this prototype.

`/health` retains its compatible liveness response. `/api/intake/health` reports opt-in state, actual Tesseract/English-data availability, limits and the process-isolation limitation. A missing runtime fails OCR jobs clearly, never as an empty successful analysis. Direct text PDFs can still work without OCR.

## Linux packaging

`Dockerfile` installs Debian Tesseract and English data, installs Python dependencies from `uv.lock`, and runs as UID 10001 with one API worker. Its `verification` target includes the test-only ReportLab dependency. Both Render manifests now select this Docker runtime with intake enabled. These are local configuration changes; hosted settings have not been applied.

```powershell
docker build --target verification -t pramana-intake-verify:local .
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m --cap-drop ALL --security-opt no-new-privileges --memory 1536m --pids-limit 64 pramana-intake-verify:local
docker build --target runtime -t pramana-intake:local .
# Disposable localhost demo only; this HTTP run has ordinary Docker networking.
docker run --rm -p 127.0.0.1:8000:8000 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m --cap-drop ALL --security-opt no-new-privileges --memory 1536m --pids-limit 64 -e PRAMANA_ENABLE_LOCAL_INTAKE=1 pramana-intake:local
```

The offline verification command denies network access and limits writable storage to disposable tmpfs. Windows Job Objects impose combined memory/process limits and terminate descendants; Linux workers use process groups and resource limits. Neither a Python subprocess nor a Windows Job Object provides filesystem/network isolation. A hosted service needs a separately confined worker and egress policy. The Docker base and apt repositories can change; record the built image digest and OS package versions for a release.

## Limits and retention

Defaults/hard ceilings: 5 MiB upload; 10 pages; 12 million decoded pixels per image/render; 60 million cumulative rendered and embedded-image pixels; 200 DPI default (72–300 configurable); 100,000 Unicode code points; 20,000 regions; 8 MiB structured/TSV output; 2 MiB per preview; 96 MiB temporary working files; 768 MiB worker memory; 60 seconds per extraction; one concurrent extraction; eight retained jobs; ten immutable versions; 15-minute lifetime. `PRAMANA_INTAKE_LIMITS` accepts validated JSON with bounded overrides. See `IntakeLimits` for exact configuration ceilings. DOCX retains 5 MiB compressed, 20 MiB expanded and 200 entries. PDFium does not expose a total expanded-stream byte counter: PDF native parsing is bounded by process memory/runtime and output limits instead.

Multipart requests are bounded before parsing, with two simultaneous upload requests and a 30-second receive timeout. Excess work returns 429. Temporary paths are random; filenames are display-only. Parsers/OCR receive local files, never document-provided commands or URLs. Worker environments exclude application credentials; parser contents and native stderr are not logged.

Original bytes, previews, versions, confirmations and PDF/image reviews live in bounded process memory. Processing files are removed after success, failure, timeout or cancellation. A periodic reaper clears retained data at expiry even without a client request. Abrupt host termination cannot promise secure erasure of underlying storage; use disposable protected storage and no confidential documents. Digests do not permit original-file replay after expiry/restart. Browser results use existing tab session storage; closing the tab clears it, and expired document reviews are rejected on load. This is not durable audit storage.

Each upload receives a random bearer capability returned once; the server stores its digest. Requests bind extraction ID, version, text digest and possession of that capability. There is no authenticated identity or organization: actor is explicitly null / `anonymous_capability_holder`. These are possession checks, not production authorization. PDF/image drafts and review metadata never enter public shared history. Private endpoints use `Cache-Control: no-store`. Original download is an authenticated attachment; previews are sanitized rendered PNGs. The existing text/DOCX demo remains unauthenticated.

## API contract

| Route | Behavior |
|---|---|
| `POST /api/intake` | Multipart `brand_id=lumadesk`, `file`; 202 with extraction ID, state, expiry and one-time access token |
| `GET /api/intake/{id}` | Poll actual state; no invented percentages |
| `GET /api/intake/{id}/pages/{page}/preview` | Rendered PNG |
| `GET /api/intake/{id}/original` | Original bytes during retention only |
| `GET /api/intake/{id}/versions/{version}` | Immutable transcription version |
| `POST /api/intake/{id}/confirm` | `{version, text_sha256, page_texts, confirm_transcription:true}`; creates a new immutable accepted version |
| `POST /api/intake/{id}/analyze` | `{version, text_sha256}`; requires current confirmed version; duplicate requests return the same run |
| `GET /api/intake/{id}/reviews/{run_id}` | Current private review metadata |
| `POST /api/intake/{id}/reviews/{run_id}/decision` | Existing human-decision payload, scoped to current version |
| `POST /api/intake/{id}/cancel` | Terminates work and expires retained data |

All ID routes require `Authorization: Bearer <access_token>`. No capability in URLs. Stale/tampered versions or unconfirmed analysis return 409; wrong possession returns 404; expired active operations return 410; oversized requests 413; invalid files/confirmation 422. Parser/runtime errors after acknowledgement produce `failed` with a safe message. Changing accepted text invalidates the current analysis; old versions remain immutable and old runs cannot receive new decisions. Duplicate identical confirmation is idempotent.

## Verification and demo

```powershell
$env:REQUIRE_REAL_OCR='1'
uv run --locked python -m pytest --tb=short
uv run --locked python -m compileall -q backend scripts
uv run --locked python scripts/verify_intake.py
uv run --locked python -m backend.tests.intake_fixtures
# frontend/:
npm.cmd run build
npm.cmd run lint
```

The generator creates `tmp/intake-fixtures/{text,scan,mixed}.pdf`, PNG/JPEG, encrypted/malformed examples and three held-out PDFs. For the judge demo: upload `scan.pdf`, select **Extract text**, compare the page preview, correct a word, attest and **Confirm transcription**, then **Analyse confirmed text**, inspect **Evidence receipts**, and record a separate **Human review** decision. Repeat with `text.pdf` and `image.png`; `encrypted.pdf` must fail without analysis. The UI journey still needs browser verification (see the dated report).

Tests cover real text/scanned/mixed PDF and PNG/JPEG parsing, no duplicate hybrid-page text, confirmation/correction/version isolation, Unicode spans, private decisions, stale/tampered requests, duplicate calls, missing OCR, low/missing confidence simulation, malformed/encrypted/empty/animated images, byte/page/pixel/text/output/region/job/version limits, expiry without reads, health responsiveness and temporary-file cleanup. Existing DOCX/text/receipt/decision regressions run in the same suite. Some platform-specific tests skip on other platforms; a skipped OCR integration test is never evidence of OCR support.

## Toolchain and sources

Selected after a real text extraction/render probe: pypdfium2 5.14.0 (PDFium 156.0.8076.0), Pillow 13.0.0 and local Tesseract CLI TSV, without an extra Python OCR wrapper. ReportLab 5.1.0 is test-only. Python wheel versions are locked. Tesseract executable and English model versions/hashes are recorded separately where configured.

- [pypdfium2 API and process/thread constraints](https://pypdfium2.readthedocs.io/en/stable/python_api.html); [licensing/platform documentation](https://pypdfium2.readthedocs.io/en/stable/readme.html): Apache-2.0/BSD-3-Clause for the wrapper; PDFium and bundled dependency notices must accompany binary distributions.
- [Tesseract CLI/TSV](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) and [Tesseract manual/license](https://github.com/tesseract-ocr/tessdoc): Apache-2.0; maintain the notices shipped with the selected runtime/models.
- [Pillow image limits](https://pillow.readthedocs.io/en/stable/reference/Image.html) and [license](https://pillow.readthedocs.io/en/stable/about.html): open-source permissive PIL/HPND-style license and bundled-library notices.
- [Docker resource, filesystem and network controls](https://docs.docker.com/engine/containers/run/).

## Remaining release gates

Browser journey verification; hosted deployment and real hosted OCR health; authenticated ownership/tenant isolation; durable storage/jobs/restart recovery; restricted production worker filesystem/network; retention/secure cleanup under crashes; wider independent OCR/layout corpus and load tests. Rotation/complex-layout edge cases and Windows memory-limit exhaustion need broader adversarial tests. This is a tested local prototype, not a private production release. The other Round 3 commitments (visual checks and persistent analytics) remain outside this task.
