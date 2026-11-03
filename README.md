# Pramana

Pramana is a pre-publication brand-governance demo built with React, TypeScript and FastAPI. Open it directly: no account, provider configuration or session is required. A short welcome checks API readiness, then opens Draft Studio. If the API cannot be reached, Retry remains available. Human review and approval remain explicit; Pramana never publishes or rewrites a draft.

Use fictional, non-sensitive content. New retained reviews belong to a shared workspace visible to all visitors. Previous private account/organization audit collections are preserved and are not exposed through the shared workspace. Anonymous decisions are labeled `anonymous_reviewer`; they do not establish a verified identity.

## Run locally

Requirements: Python 3.12+, uv and Node.js compatible with the locked Vite version.

```powershell
uv sync --locked --all-groups
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
Set-Location frontend
npm ci
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open the printed Vite URL. `/ready` checks configured storage, `/health` reports the selected metadata backend, and `/docs` describes the public API. The frontend needs only `VITE_API_BASE_URL`. Keep real environment files and encryption/storage credentials outside Git. Old Firebase, cookie, membership and audit identity settings are unused and may be removed from private configuration manually; this change does not edit private files or cloud settings.

## Review workflow

- Paste text or import ordinary-paragraph DOCX, up to 5 MiB and 100,000 extracted characters. DOCX parsing runs in the existing bounded subprocess. Unsupported macros/embedded payloads, unsafe filenames, malformed XML and oversized packages return safe errors.
- Optional local PDF/PNG/JPEG intake preserves per-file hashes, page provenance, previews, OCR warnings and immutable transcription versions. Review and confirm the transcription before analysis. See [intake limits and setup](docs/pdf-image-intake.md).
- Four deterministic LumaDesk checks use approved versioned rules and sources. Validation checks exact draft quotes/spans, source excerpts, rule identity and deterministic applicability. Duplicate findings at the same location are removed; separate locations remain separate.
- The only evidence states are Supported, Contradicted, Unsupported (needs verification), and Indeterminate (needs verification). Findings cover configured checks, not general factual accuracy or certification.
- Human Review records approved, revision or rejected only after a separate explicit action. No external AI service is used.
- [Visual Checks](docs/visual-checks.md) offers bounded rendered styles as well as the original static checks. Chromium measures inherited colors, contrast, font size/weight and geometry with supplied scripts and external requests disabled. The fictional LumaDesk sample works with its bundled policy; real brands require an approved manifest. Unresolved effects remain indeterminate.

## Storage

With no MongoDB, shared metadata history is limited to 100 runs in process memory and disappears on restart. Optional `MONGODB_URI`/`MONGODB_DB` persist text/DOCX metadata and decisions; metadata history does not retain drafts or receipts. PDF/image extraction and capability-protected reviews remain local and expiring.

Optional [retained audit storage](docs/audit-and-analytics.md) uses existing MongoDB encryption/retention settings. It preserves evaluated drafts, evidence, human decisions and analytics in a new shared collection. The frontend selects this mode from `/ready`. Original-file storage is optional; see [storage setup](docs/storage-deployment.md). A configured unavailable database returns an error; there is no silent fallback to memory.

## Verification

```powershell
uv run pytest
uv run python -m compileall -q backend
Set-Location frontend
npm test
npm run lint
npm run build
```

See [the local change report](docs/no-auth-loading-and-engine.md) for exact results and limitations. Local tests do not establish deployed behavior or production privacy, durability or OCR accuracy. No push, deployment or cloud changes are part of this update.

The latest [three-feature acceptance report](docs/mandatory-feature-verification.md) supersedes the earlier report's browser and real-database verification gaps. To install the renderer runtime locally, run `uv run playwright install chromium` after the locked dependency installation. On Linux, use `uv run playwright install --with-deps --only-shell chromium`; the Dockerfile includes this setup. The container build itself still needs independent verification.

To use retained audit locally, preserve existing private keys and load both private files: `uv run --env-file .env --env-file .env.audit uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`. Add `--env-file .env.bunny` only when original-file storage is configured. `/ready` must report `audit: true` for retained evidence and analytics; metadata-only mode does not provide those guarantees.
