# PDF/image verification — 3 November 2026

Local implementation on `codex/pdf-image-intake`, based on `1dd8ae5`. No commits, pushes, account changes or deployment were performed. The pre-existing untracked prompt directory was preserved.

## Actual checks

| Check | Result |
|---|---|
| Before changes: locked backend pytest | 54 passed; one existing Starlette/httpx deprecation warning |
| Final Windows suite: `$env:REQUIRE_REAL_OCR='1'; uv run --locked python -m pytest --tb=short` | 94 passed in 32.32 s; one existing deprecation warning; real OCR enabled |
| `uv run --locked python -m compileall -q backend scripts` | Passed |
| `npm.cmd run build` in `frontend` | Passed, TypeScript and Vite production bundle |
| `npm.cmd run lint` | Passed with the two pre-existing React-effect warnings in AuditTrailPage and BrandGuidelinesPage; no new warnings |
| Docker verification image | Built successfully with Python 3.12, locked dependencies, Debian Tesseract and English data |
| Linux offline container suite | 93 passed, 1 skipped in 32.62 s; skipped test is Windows Job Object containment; all real OCR tests ran. Container used `--network none --read-only`, tmpfs, dropped capabilities, no-new-privileges, 1536 MiB memory and 64 PIDs. |
| Browser journey | **Blocked / unverified**: browser access host unavailable; native browser access stopped because it could not reliably determine the current URL for policy enforcement. No alternate UI automation was attempted. |
| Hosted deployment | **Not performed**. Existing Render Python configuration does not install OCR. |

The initial Windows environment required execution permission for uv's Python trampoline; running the locked environment resolved it. During implementation, real fixtures exposed and fixed PDFium page/bitmap cleanup and image-size API mismatches. A final test initially compared separately generated timestamped PDF bytes; it was corrected to reuse identical bytes, then the complete Windows suite passed. These are fresh results, not the historical README count.

After those complete suites, cancellation was adjusted to release a retained-job slot immediately after its worker exits. The two affected Windows workflow/capacity tests passed (2.33 s); compilation and `git diff --check` passed again. The Linux image predates that final small cancellation adjustment. A production runtime image/HTTP healthcheck and hosted deployment were not exercised; the container verification target exercised API and OCR health through TestClient.

## Quality and timing measurements

Command: `uv run --locked python scripts/verify_intake.py`. Raw per-file results, hashes, runtime versions and settings are in [pdf-image-intake-measurements.json](pdf-image-intake-measurements.json).

- Held-out text PDFs: three two-page files, 18 total paragraphs; **18/18 recovered in order**, no missing expected paragraphs, whitespace-normalized text exactly matched. This exceeds the plan's 95% target **on this small simple-layout fixture set only**. It does not establish universal PDF recovery.
- Real OCR: one scanned PDF, one PNG and one JPEG; all nine expected paragraphs recovered, normalized text matched exactly for these clean printed samples. Mixed text/scan/hybrid PDF behavior also passed integration tests. No real-world OCR accuracy or rule-engine accuracy is inferred from this sample.
- Local API TestClient timings: upload acknowledgement 2.4–7.2 ms; two-page text extraction 0.78–0.91 s; OCR 1.40–1.96 s; deterministic analysis 3.0–8.6 ms. These are individual observations, not HTTP-network/deployment latency, p95/p99, load measurements or performance improvements. Other tests/builds were running on the same machine.
- Windows toolchain: Python 3.14.6; pypdfium2 5.14.0 / PDFium 156.0.8076.0; Pillow 13.0.0; Tesseract 5.5.3.20260724. English model SHA-256 is recorded in the raw report. Docker uses the Debian-packaged OCR runtime, which can differ.

## Changed areas

Backend: `intake_models.py`, `intake_api.py`, `extraction_store.py`, `intake_process.py`, `intake_worker.py`, `pdf_image_intake.py`; small integration changes in settings, main and response schemas. Existing engine/validator/domain/seeded-rule code was preserved.

Frontend: typed intake API/access handling; `DocumentIntakePanel` for processing, previews, corrections, confirmation and analysis; `DocumentProvenance` for receipts/review; workspace upload integration; Unicode code-point receipt highlighting; private document decisions; small matching CSS additions.

Verification/setup: fictional fixture generator, 40 new tests, measurement script, locked parser/image dependencies, test-only ReportLab, Dockerfile/.dockerignore, `.env.example`, README/test-matrix updates and the intake guide.

## Handoff and remaining gates

Use [the setup/API guide](pdf-image-intake.md) for exact startup commands and the short judge demo. Local test API and Vite were started at `127.0.0.1:8000` and `127.0.0.1:5173`. Intake requires explicit local opt-in and Tesseract paths. Machine-local OCR binaries and generated fixtures are in ignored `tmp/`; other machines must install the runtime.

The implementation is a bounded local prototype. Remaining release blockers: browser journey completion; hosted OCR deployment/health; authenticated ownership and tenant isolation; durable jobs/private storage/restart recovery; production worker filesystem/network confinement; wider adversarial/layout/rotation coverage and load testing. Original replay expires with the bounded memory store. Anonymous upload capabilities are not authenticated user identity. The other Round 3 commitments are not implemented by this task.
