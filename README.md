# Pramana

**Authentication update:** application access now requires a verified Firebase account. The landing page introduces Pramana and supports email/password signup/login, Google, GitHub, verification guidance and password reset. Private APIs require server-verified session cookies; new accounts receive isolated personal workspaces and organization roles require explicit server-controlled membership. Shared demo routes are closed to the new flows. **Start with [authentication setup, security boundaries and the configuration checklist](docs/authentication.md)** before using the app. Older demo/operator-key descriptions below describe the preserved legacy implementation, not an unauthenticated access option.

Pramana is a small brand-governance demo. It checks a draft against a fictional brand's approved terminology, prohibited phrase, one plan fact, and disclaimer rule. Each returned finding includes a rule and source reference; a human can inspect the receipt and record a review decision.

**Status:** PDF/image intake is an opt-in local prototype. Authenticated audit mode adds organization-scoped encrypted evidence retention, durable decisions, history and analytics; see [audit setup and verification](docs/audit-and-analytics.md). Optional legacy MongoDB metadata storage remains available separately; see [MongoDB setup](docs/mongodb-setup.md). See [intake setup and release gates](docs/pdf-image-intake.md) and [intake verification](docs/pdf-image-intake-verification.md). This is not a production certification or general-purpose fact/legal check. Hosted access, key management, backups and durability must be verified in your deployment.

## What works

- React, TypeScript, and Vite frontend connected to a FastAPI API.
- Paste text or upload a `.docx` containing ordinary paragraphs. Opt-in PDF/PNG/JPEG intake adds local OCR, page previews, transcription correction and mandatory confirmation before analysis. See the linked limits; complex layout reconstruction is not promised.
- Four deterministic checks for the fictional LumaDesk brand, with version-pinned rules, sources, excerpts, and candidate validation.
- Evidence Receipts display the exact evaluated draft and matching passage when applicable.
- Reviewer can record `approved`, `revision`, or `rejected`; history shows finding counts and decision events.
- Without `MONGODB_URI`, history retains at most 100 runs in process memory and is lost on restart. With MongoDB, text/DOCX metadata and decisions persist and history returns the latest 100 runs. Draft text and receipts are not retained; PDF/image jobs and their private reviews remain volatile. The MongoDB demo caps each run at 100 decision events; further decisions return 409. Retention/deletion policy and authenticated ownership remain release work.
- No LLM or external analysis API is used.
- Authenticated organization audit mode retains encrypted evaluated text, evidence and configuration snapshots, conflict-safe human decisions, restart-safe paginated history and real analytics. See [audit setup, API and verification](docs/audit-and-analytics.md). It requires MongoDB, operator-issued access keys and encryption/retention configuration; the shared demo remains separate.
- Bounded backend static visual checks: exact logo asset hashes, configured CSS palette targets, declared-color contrast and HTML image descriptions. Requires an operator-approved manifest; see [API, setup, supported scope and limits](docs/visual-checks.md). Rendered-page evaluation is not implemented.

## Run locally

Requirements: Python 3.12+, `uv`, and Node.js compatible with the checked-in Vite version.

From the repository root, start the backend in PowerShell:

```powershell
uv sync --locked --all-groups
# First setup only: preserve an existing .env and its private credentials.
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

Configure the Firebase settings and MongoDB/encryption keys in [the authentication guide](docs/authentication.md), including `PRAMANA_COOKIE_SECURE=0` for loopback HTTP development. Open the Vite URL printed by the command. The API is at `http://127.0.0.1:8000`; `/docs` also requires a valid session. Missing authentication configuration leaves the landing page available but cannot authorize application access.

## Configuration

The backend reads `CORS_ORIGINS`, a comma-separated list of exact browser origins. Local defaults are in `.env.example`. Optional `MONGODB_URI` and `MONGODB_DB` enable MongoDB metadata storage. A configured but unavailable database fails startup; it never silently falls back to memory. `/health` pings the selected database and returns `mongodb_review_metadata` when ready. `DATABASE_URL` remains reserved and unused. The frontend reads `VITE_API_BASE_URL`; locally, set it to the API origin as shown above.

Never put a real `.env` file, credentials, or secrets in Git. The browser now signs in through Firebase and uses HttpOnly session cookies; it does not ask for organization keys. Authenticated `/api/audit` APIs use separate workspace-scoped storage and encrypted evidence with explicit retention. Legacy shared records are inaccessible through the new flows. Follow [the hosting checklist](docs/authentication.md#one-time-configuration-checklist): same-site HTTPS or a same-origin API proxy is required for the chosen cookies.

## Deployment preparation

MongoDB/audit and private Bunny original-file deployment: see [storage setup and actual verification](docs/storage-deployment.md). New deployment checks are `/ready` and `scripts/check_audit_deployment.py`; Bunny integration requires a separately configured private Storage zone and live verification.

The backend and frontend are configured together in [`render.yaml`](render.yaml). The clean project is published publicly at [github.com/ananyap-20/Pramana](https://github.com/ananyap-20/Pramana) on `main`; no hosting service has been created yet.

1. Create the Render Blueprint from the repository root; it defines a free Python API web service and a free static frontend.
2. Set `CORS_ORIGINS` to the exact deployed frontend origin, including `https://` and without a trailing slash. Set the frontend's `VITE_API_BASE_URL` to the deployed API origin, also without a trailing slash, then redeploy both services.
3. Verify the API `/health` endpoint, open the frontend, submit the sample, inspect receipts, record a decision, and confirm history.

Deployment attempt status (2026-10-29): Render blocked Blueprint creation with an account-level card-verification modal and hCaptcha. No services or live URLs were created, and no payment details were entered. The repository and free-tier Blueprint remain ready; continue only after the account-level checks are completed manually.

Platform terms checked against official docs on 2026-10-29: [Render free services](https://render.com/docs/free), [Render static sites](https://render.com/docs/static-sites), and [Render Blueprint YAML](https://render.com/docs/blueprint-spec). Render static sites are free to deploy. Free web services sleep after 15 minutes without traffic, take about a minute to wake, have ephemeral local filesystems, receive 750 free instance hours per workspace each calendar month, and are not recommended for production. Check current provider terms and billing settings before deployment; no cost is guaranteed by this repository.

Shared demo history and decisions remain unauthenticated and suitable for fictional content. Authenticated audit mode must be configured separately and accessed through `/api/audit`. It retains completed review evidence and decisions; PDF/image extraction jobs and original uploads remain volatile. A free sleeping web service is a demo deployment, not proof of production readiness.

## Verification

From the repository root:

```powershell
uv run pytest
uv run python -m compileall -q backend
Set-Location frontend
npm ci
npm run build
```

Verified for this project snapshot: **54 backend tests passed**, Python compilation passed, and the Vite production build passed. Pytest reported one Starlette/httpx deprecation warning. See [`docs/test-matrix.md`](docs/test-matrix.md) for tested behaviors and the local browser journey.

The test pass rate describes this synthetic regression suite only; it does not measure real-world detection precision or recall.

## Project material

- [`docs/pramana_summary.html`](docs/pramana_summary.html): print-ready, three-page technical report.
- [`docs/pramana_workflow.svg`](docs/pramana_workflow.svg): implemented workflow diagram.
- [`docs/round3-roadmap.md`](docs/round3-roadmap.md): three proposed improvements with estimates and success measures.
- [`docs/evaluation.md`](docs/evaluation.md): synthetic evaluator scenarios and limits.
- [`docs/optimization-report.md`](docs/optimization-report.md): factual architecture and implementation notes.

No license has been added. The supplied archive's old Git remote pointed to `teclium28-jpg/Pramana`; that history was excluded. The published repository starts with a fresh `main` branch under the requested `ananyap-20` account.
