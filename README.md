# Pramana

Pramana is a small brand-governance demo. It checks a draft against a fictional brand's approved terminology, prohibited phrase, one plan fact, and disclaimer rule. Each returned finding includes a rule and source reference; a human can inspect the receipt and record a review decision.

**Status:** local demo verified on 2026-10-29. It is not a production service and does not provide general-purpose fact checking, authentication, durable audit storage, or legal review.

## What works

- React, TypeScript, and Vite frontend connected to a FastAPI API.
- Paste text or upload a `.docx` containing ordinary paragraphs. Plain `.txt`, `.md`, `.pdf`, image, table, and OCR intake are not supported.
- Four deterministic checks for the fictional LumaDesk brand, with version-pinned rules, sources, excerpts, and candidate validation.
- Evidence Receipts display the exact evaluated draft and matching passage when applicable.
- Reviewer can record `approved`, `revision`, or `rejected`; history shows finding counts and decision events.
- Local history retains metadata for at most 100 runs in the current server process. It does not store draft text or receipt passages and is lost on process restart.
- No LLM or external analysis API is used.

## Run locally

Requirements: Python 3.12+, `uv`, and Node.js compatible with the checked-in Vite version.

From the repository root, start the backend in PowerShell:

```powershell
uv sync --locked --all-groups
Copy-Item .env.example .env
uv run uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
Set-Location frontend
npm ci
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open the Vite URL printed by the command. The API is at `http://127.0.0.1:8000`; interactive API docs are at `/docs`.

## Configuration

The backend reads `CORS_ORIGINS`, a comma-separated list of exact browser origins. Local defaults are in `.env.example`. `DATABASE_URL` is reserved and unused by this in-memory demo. The frontend reads `VITE_API_BASE_URL`; locally, set it to the API origin as shown above.

Never put a real `.env` file, credentials, or secrets in Git. The API returns the submitted draft to the requesting browser for review, but the demo repository stores only run metadata, counts, and decisions. Do not submit confidential material: the service has no authentication, and other visitors to the same running instance can read history summaries and change decisions if they know a run ID.

## Deployment preparation

Configuration is prepared in [`render.yaml`](render.yaml) and [`frontend/vercel.json`](frontend/vercel.json). The clean project is published publicly at [github.com/ananyap-20/Pramana](https://github.com/ananyap-20/Pramana) on `main`; no hosting service has been created yet.

1. Deploy the repository root as a Render Python web service using the Blueprint. Set `CORS_ORIGINS` to the exact deployed Vercel origin, including `https://` and without a trailing slash.
2. Import the same repository into Vercel with **Root Directory** set to `frontend`. Set `VITE_API_BASE_URL` to the deployed Render API origin, without a trailing slash, then deploy.
3. Verify `/health`, open the frontend, submit the sample, inspect receipts, record a decision, and confirm history.

Platform terms checked against official docs on 2026-10-29: [Render free services](https://render.com/docs/free), [Render Blueprint YAML](https://render.com/docs/blueprint-spec), [Vercel Hobby](https://vercel.com/docs/plans/hobby), and [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json). Render free web services sleep after 15 minutes without traffic, take about a minute to wake, have ephemeral local filesystems, receive 750 free instance hours per workspace each calendar month, and are not recommended for production. Vercel Hobby is restricted to personal, non-commercial use; confirm the project qualifies before using it. Confirm both providers' current terms and billing settings before deployment; no cost is guaranteed by this repository.

The backend has no authentication or rate limiting. Its shared process-local decision/history store is suitable only for a disposable public demo with fictional/sample content, not private drafts or audit requirements. Render restarts, redeployments, and spin-downs can clear history.

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
