# MongoDB connection and deployment walkthrough

For the new authenticated audit, retained evidence and analytics implementation, use [audit setup and verification](audit-and-analytics.md). This page describes the earlier shared metadata mode, which remains separate and unauthenticated.

Prepared 3 November 2026 for the existing project at `C:\Users\Ishaan\OneDrive\Pramana`.

## Scope and actual verification

The code now optionally stores text/DOCX review metadata and human decisions in MongoDB's `review_runs` collection. Brand rules still come from the approved fictional seed configuration. Original drafts, evidence receipts, uploaded documents, OCR jobs and PDF/image review histories are not persisted by this change. Nothing approves or publishes content automatically.

Without `MONGODB_URI`, the existing bounded memory demo is preserved. With a configured URI, MongoDB startup failure is an error, never an automatic memory fallback. `/health` reports `mongodb_review_metadata` only after a successful ping. History returns the latest 100 records; stored records are not automatically deleted. Decisions append atomically to the run document, with a 100-event cap per run. This is not a complete authenticated, idempotent, version-conflict-aware audit system, and there is no organization isolation or automatic retention policy yet.

Verification: the full Windows offline suite passed with 101 tests and one existing Starlette/httpx deprecation warning. Frontend build passed; lint passed with its two existing React-effect warnings. Tests use a mocked MongoDB collection for adapter/API contracts, not a real MongoDB server. The assistant did not read `.env`, load credentials, contact Atlas, push commits, provision services, or deploy. The live Atlas and hosted checks below must still be run by the user. The Windows sandbox blocked Python's local event-loop socketpair; offline tests passed when run outside it.

## 1. Check Atlas from your laptop

1. Open PowerShell from the Windows Start menu.
2. Run:

```powershell
Set-Location 'C:\Users\Ishaan\OneDrive\Pramana'
uv sync --locked --all-groups
uv run --env-file .env python scripts/check_mongodb.py
```

You run this command yourself: it supplies your saved `.env` values to the script. It never prints the connection string or password. It creates one fictional test review, appends a decision, opens a new MongoDB connection, verifies the record and decision, and removes only that test review. It also initializes the application history index. It does not establish backup restoration or hosted persistence.

Success includes `PASS: connected to MongoDB` and `PASS: review metadata and human decision survived a new database connection.` Do not proceed on FAIL.

If it fails, open Atlas → your project → Security → Database & Network Access:

- Under IP Access List, add your laptop's current public IP; update it if your internet connection changes.
- Under Database Users, confirm your database user has read/write privileges for `pramana`, is restricted to the intended cluster, and has not expired.
- Privately check the URI's password placeholder and URL encoding of reserved characters. Keep the actual Atlas hostname and connection options.
- If the script says the URI is missing, check the variable is named `MONGODB_URI` and the file is `.env`, not `.env.txt`.

Never paste credentials into chat or commit `.env`. Share only the script's safe PASS/FAIL lines.

## 2. Start and test the local API

In PowerShell run:

```powershell
uv run uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

Leave that window open. Open `http://127.0.0.1:8000/health` in your browser. Expected:

```json
{"status":"ok","persistence":"mongodb_review_metadata"}
```

An in-memory response means the new app process did not receive `MONGODB_URI` or you reached an older running server. If port 8000 is occupied, stop your old local API with Ctrl+C in its own terminal, then rerun this command.

Open `http://127.0.0.1:8000/docs`:

1. Expand `POST /api/reviews/analyze`.
2. Click Try it out and enter:

```json
{"brand_id":"lumadesk","draft_text":"Our dashboard is guaranteed to eliminate all errors."}
```

3. Click Execute. Copy the returned `review_run_id` privately for the next call.
4. Expand `POST /api/reviews/{review_run_id}/decision`, click Try it out, paste the run ID, set the body to `{"decision":"revision"}`, and Execute.
5. Expand `GET /api/reviews/history/{brand_id}`, click Try it out, enter `lumadesk`, and Execute. Confirm the run and revision event appear.
6. Stop the API with Ctrl+C, start it with the same command, and fetch history again. The same run and decision should remain.
7. In Atlas, open Browse Collections/Data Explorer → `pramana` → `review_runs` and confirm the run exists. Metadata contains no original draft or receipt text.

## 3. Publish the prepared source branch

Do this only after the local checks pass. The starting checkout is `codex/pdf-image-intake` and includes the committed PDF/image work. A new branch preserves that history and includes these MongoDB changes.

In a second PowerShell window run:

```powershell
Set-Location 'C:\Users\Ishaan\OneDrive\Pramana'
git switch -c codex/mongodb-history
git add -- .env.example README.md pyproject.toml uv.lock backend/app/config.py backend/app/main.py backend/app/repositories/demo_repository.py backend/app/repositories/mongodb_repository.py backend/tests/test_mongodb_repository.py scripts/check_mongodb.py docs/mongodb-setup.md frontend/src/components/TopBar.tsx frontend/src/pages/AuditTrailPage.tsx frontend/src/pages/DraftWorkspacePage.tsx
git diff --cached --stat
```

Review the file list. `.env` must not appear. Then:

```powershell
git commit -m "Add optional MongoDB review metadata persistence"
git push -u origin codex/mongodb-history
```

If Git reports that the branch exists, switch to that branch instead of creating it again, after checking for unrelated local changes. If a push is denied, ask the repository owner for collaborator access; do not replace the remote or force-push. This source branch is what you select on Render. A public-source push and deployment are user actions, not actions already performed by the assistant.

To release the matching frontend source too, open the repository on GitHub, select Compare & pull request for `codex/mongodb-history`, choose base `main`, review the file list and checks, and create the pull request. Merge it when ready. Existing services tracking main may redeploy. After merging, use `main` as the Render deployment branch below. In the Vercel frontend's Git settings, verify that it is connected to this repository and the intended production branch. If it uses another repository, stop and reconcile its source before claiming the new UI copy is deployed.

## 4. Create the backend web service

The existing frontend can remain on Vercel. The user confirmed the backend is on Vercel Hobby. Vercel's Static IP option is on Pro/Enterprise; using Render's documented outgoing ranges avoids requiring that paid Vercel feature for Atlas IP allowlisting. This is a proposed backend hosting change, not a claim that Render is already deployed. Render Free sleeps after inactivity; it is appropriate only for a bounded demo with the limitations below.

1. Open https://dashboard.render.com/ and sign in.
2. Select New → Web Service.
3. Connect GitHub and authorize the `ananyap-20/Pramana` repository. The repository owner may need to grant access.
4. Select that repository and branch `main` after merging the reviewed source changes as described above.
5. Give the service a name such as `pramana-api`. The actual assigned hostname may differ.
6. Choose Python 3 as the language/runtime and leave Root Directory blank.
7. Choose a region near your Atlas cluster. The supplied screenshot showed Atlas in Mumbai; choose a nearby offered region, such as Singapore, rather than assuming the Vercel frontend region controls database location.
8. Enter Build Command:

```sh
pip install uv==0.11.25 && uv sync --locked --no-dev
```

9. Enter Start Command:

```sh
uv run --no-sync uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT
```

10. Select the Free instance type explicitly.
11. Under environment variables add `CORS_ORIGINS=https://20ananyapandey.vercel.app` and `PRAMANA_ENABLE_LOCAL_INTAKE=0`.
12. Do not add the MongoDB URI yet. Deploy once in memory mode so you can obtain the service's outbound ranges before enabling the database.
13. Click Create Web Service and wait for the build/deployment to finish. If account/card verification blocks creation, resolve it manually or stop at that blocker; do not assume this was bypassed or that a paid plan is required/authorized.
14. Record the exact HTTPS service URL Render assigns. Set the health-check path to `/health` in service settings if available.

PDF/image intake is deliberately disabled on this native Python deployment. Installing Tesseract, durable private file storage, isolated workers and hosted OCR verification are separate release work; enabling an environment flag does not install them.

## 5. Allow Render to access Atlas, then enable MongoDB

1. In Render, open the service details.
2. Open Connect, then the Outbound tab.
3. Copy every listed IP/CIDR range. These ranges may be shared with other services in the region; the database password and privileges are still required.
4. In Atlas, open Database & Network Access → IP Access List → Add IP Address.
5. Add each Render range exactly, labeling it `Pramana API Render`. Do not enter the website IP or add all internet addresses.
6. In Render, open Environment → Add Environment Variable.
7. Add `MONGODB_URI` with the same private connection string you saved locally.
8. Add `MONGODB_DB=pramana`.
9. Save and redeploy using the latest source commit.
10. Open the assigned service URL followed by `/health`. Require `mongodb_review_metadata`, not the in-memory marker.

## 6. Point the frontend to the new backend

1. Open https://vercel.com/dashboard and select the frontend project for `20ananyapandey.vercel.app` (not the old backend project).
2. Open Settings → Environment Variables.
3. Find `VITE_API_BASE_URL` and edit it, or add it if absent.
4. Set its value to the actual new Render HTTPS service URL, with no `/health`, `/docs` or trailing slash. Apply it to Production.
5. Save. Open Deployments, select the latest production deployment's menu, choose Redeploy, and confirm Production.
6. Open the public frontend and analyse the fictional sample. Check the browser's F12 → Network → Fetch/XHR panel: analysis calls must go to the new Render URL.
7. Record a revision decision and confirm the run in history.

Updating a Vite environment variable requires rebuilding/redeploying the frontend. The old Vercel backend is left intact as a fallback; it is not migrated, disabled, or made durable by these steps. Historical in-memory records cannot be recovered from a stopped old process by adding MongoDB now.

## 7. Verify hosted durability and the domain later

1. Save a test run ID from the public frontend's analysis response.
2. Redeploy the Render backend from its dashboard.
3. Wait for `/health` to return the MongoDB marker again.
4. Refresh frontend history and verify that exact run ID and decision remain.
5. Verify the record in Atlas. Capture the deployed commit, health response, and test result for the report without secrets.

Only after that hosted journey works, attach your purchased domain to the frontend, add an API subdomain to the backend host, and update `VITE_API_BASE_URL` and `CORS_ORIGINS` to their final HTTPS addresses. Domain purchase/DNS instructions are separate; no actual domain was supplied or configured in this change.

## Limits and remaining production gates

This finishes a metadata-persistence slice, not the entire production roadmap. All users still share an unauthenticated demo history and can submit decisions for known IDs. Retention, deletion, organization separation, reviewer identity, optimistic decision conflicts, idempotency, immutable evidence replay, database backup/restore, load testing and operational monitoring remain required. A changed decision appends an event; it is not a signed or tamper-proof audit record.

Free Render web services sleep after 15 minutes of inactivity and can take about a minute to wake. Atlas metadata remains external, but the app still needs an always-running hosting choice and measured capacity for production. Never claim hosted OCR or restored backups based on a database ping or the reconnect smoke script.

## Official references

- Atlas IP access list: https://www.mongodb.com/docs/atlas/security/ip-access-list/
- Atlas database users: https://www.mongodb.com/docs/atlas/security-add-mongodb-users/
- PyMongo connection options: https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html
- Vercel networking plan options: https://vercel.com/docs/networking
- Render FastAPI: https://render.com/docs/deploy-fastapi
- Render outgoing ranges: https://render.com/docs/outbound-ip-addresses
- Render Free limits: https://render.com/docs/free
