# Durable audit and analytics

Implemented 3 November 2026 on the preserved `00f8ad8` intake baseline, alongside the existing uncommitted MongoDB and static visual work. MongoDB remains the deliberate NoSQL choice from backend plan section 7. No commits, remote writes or deployments were performed.

## Behavior and boundaries

The authenticated `/api/audit` path retains completed text, DOCX and confirmed PDF/image analysis results, exact evaluated text, validated receipts and the evaluated brand configuration/source versions. Snapshots are encrypted with AES-256-GCM. Metadata pins draft ID/version/digest, engine/configuration digest/version, actor, request identity, times and retention expiry. Reopening a review after application/database restart uses its saved snapshot, not current draft text or current rules. Stored hashes are verified against decrypted evidence.

Every audit request authenticates an operator-issued 256-bit access key. The server keeps its SHA-256 digest and maps it to an actor, organization and role. Organization identity comes exclusively from that mapping, never a request field. Readers can read; reviewers/admins can analyze and decide; only admins can delete retained runs. These are bounded operator-managed memberships, not self-service accounts, passwords, SSO or MFA. Do not share keys between reviewers. Revoke/rotate access by changing the configured digest mapping and restarting the backend.

Audit data uses a separate `audit_reviews_v1` collection. Legacy shared demo routes never read or update it, and prior records are not silently migrated into an authenticated organization. Without the required audit configuration, audit routes return 503; there is no memory fallback. `/health` still describes legacy repository storage. Authenticated `/api/audit/me` reports the audit identity, retention and `mongodb_encrypted_audit` mode. The browser uses audit routes only after an organization key is connected; invalid/revoked access never silently falls back to the demo path.

PDF/image extraction and confirmation retain their existing capability-token boundary. Saving a confirmed review requires both organization reviewer access and that upload's token. Completed text/receipt/configuration snapshots survive separately from the temporary extraction job. Original binary uploads, previews, ongoing extraction jobs and static visual-only measurements are not persisted here. No queue/outbox was introduced because completed review+evidence registration is one MongoDB write; durable extraction scheduling remains separate work.

## Setup

1. Install the locked environment: `uv sync --locked --all-groups`. `cryptography` is the sole new direct dependency for authenticated snapshot encryption.
2. Keep the existing private `MONGODB_URI` / `MONGODB_DB` in `.env`. Use an application database, explicit network allowlists, TLS to hosted MongoDB and least-privilege database credentials. No Atlas settings are changed by this implementation.
3. Generate fresh audit credentials **once**, without overwriting existing keys:

   ```powershell
   uv run --locked python scripts/create_audit_credentials.py --actor reviewer1 --organization team1 --role reviewer
   ```

   This creates ignored `.env.audit` (server configuration) and `.env.audit.access-key` (the user's bearer key), without printing secrets. Exclusive creation refuses an existing output. POSIX files use mode 0600; on Windows protect them with appropriate user-only ACLs. Keep encryption keys in your secrets manager with a recoverable backup, separate from database backups. Give each reviewer a distinct bearer key through a secure channel. Never put either private file in Git.

4. Start the backend with both files:

   ```powershell
   uv run --locked --env-file .env --env-file .env.audit uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
   ```

   The multiple `--env-file` syntax was checked with the installed uv. Existing README frontend startup commands apply. Connect the issued key in the application's audit-access form, analyze a draft, open Human review, record a decision, then open Audit and analytics. Reconnect using the same key after closing the browser tab.

For additional users, add independently generated `secrets.token_urlsafe(32)` keys to the identity mapping using their SHA-256 digests. Preserve the existing encryption key ring: do not regenerate the whole configuration to add a user. Each identity has `token_sha256`, `actor_id`, `organization_id`, and `role` (`reader`, `reviewer`, `admin`). IDs use 1–64 letters/digits/underscores/hyphens. At most 100 active keys are configured. Map each key to exactly one organization; a user with multiple memberships uses separate keys. Role revocation takes effect on backend restart.

Required settings are `PRAMANA_AUDIT_IDENTITIES`, `PRAMANA_AUDIT_KEYS` (key ID -> base64 32-byte key), `PRAMANA_AUDIT_ACTIVE_KEY`, and MongoDB. Optional `PRAMANA_AUDIT_RETENTION_DAYS` is 1–90, default 30. Partial/invalid configuration fails startup. A missing/decrypt-incompatible key never yields an empty successful review.

## Storage and event integrity

Each review document contains immutable initial metadata, encrypted evidence and a bounded append-only decision array. The application never replaces an earlier decision or rewrites a draft. Each decision records UUID, actor, UTC time, revision and request key. BSON millisecond precision is applied before returning the event so retries return identical JSON.

Analysis requests require `Idempotency-Key` (16–100 ASCII letters/digits/underscores/hyphens). A unique `(organization_id, request_id)` index makes analysis registration atomic across callers. The same key+actor+payload replays the original result; changed payload conflicts with 409. Keys are reserved for the retention period. After expiry/TTL deletion, use new keys; permanent idempotency after deletion is not promised.

Decisions require a key and `expected_revision`. An atomic conditional `$push` + `$inc` either appends exactly one event or returns 409. Same-key retries replay the original event, including after later revisions. Changed payload/actor with a reused key conflicts. Decision keys are scoped to organization and the concrete run decision endpoint. Competing reviewers cannot silently replace each other's decisions. Corrections append events. At 100 events, further decisions return 409. The array and revision are changed in the same document; latest outcome is derived from the last event, avoiding a separate summary write or multi-document transaction.

MongoDB writes use `w=majority, j=true`; reads use majority concern. Application startup creates unique, organization/history and expiry indexes. History and decision reads exclude encrypted snapshots to avoid transferring them unnecessarily. No draft content is logged. Request validation and driver failures return safe errors. Requests authenticate before body parsing, have bounded upload sizes/time and four active requests per application process. Organization history uses keyset pagination, 25 records by default, at most 100 per page.

## Retention, deletion and recovery

`expires_at` is fixed when a run is created, using the configured retention period. Every audit read/write/aggregate excludes expired records immediately; the MongoDB TTL index physically deletes them asynchronously. Restarting or changing the default does not extend existing expiry. Admin `DELETE` removes the entire organization's matching run (encrypted evidence, metadata and events) and is idempotent. It is a no-op for unknown/other-organization IDs. There is no undo in this application.

Database operators must retain encrypted backups and all still-needed decryption keys separately. Key rotation: add a fresh key ID, select it as active, retain old key IDs until all associated snapshots/backups expire. Removing an old key prematurely makes those snapshots unreadable. Do not reuse a nonce/key combination; encryption uses a fresh random 96-bit nonce per snapshot. Organization and run IDs are authenticated as associated data, preventing ciphertext swapping between runs/organizations.

Backup/restore exercise: take `mongodump --archive=<protected-file> --db=<database>` with a properly authorized operator; restore into a **separate** authorized database with `mongorestore --archive=<protected-file> --nsFrom='<source>.*' --nsTo='<restore>.*'`; retain keys, run application startup/index checks, verify one known run's decrypted snapshot, actor/revision and analytics, then authorize any switch to the restored service. Never restore over the live database as an unreviewed verification step. Follow your backup expiry/deletion policy too: application deletion cannot erase an offline backup. Restored expired records remain inaccessible even before TTL cleanup.

Application-enforced append-only events are not a cryptographically immutable audit log. Privileged database administrators can alter/delete metadata and events. Hosted backups, disaster recovery, secure key custody, HTTPS, production identity provisioning and deployment monitoring remain operational responsibilities; local acceptance tests do not certify those systems.

## API contract

All routes require `Authorization: Bearer <access-key>` and return `Cache-Control: no-store`. OpenAPI includes a Bearer security scheme. JSON validation errors are sanitized; database failures return 503 without driver credentials/addresses.

| Route | Behavior |
|---|---|
| `GET /api/audit/me` | Authenticated actor, organization, role, retention, persistence |
| `POST /api/audit/reviews/analyze` | `{brand_id,draft_text}` plus request key; durable `AnalyzeResponse` |
| `POST /api/audit/reviews/analyze-document` | Multipart `brand_id`, supported DOCX `file`, request key |
| `POST /api/audit/intake/{id}/analyze` | Confirmed `{version,text_sha256}`, request key and `X-Intake-Token`; retains server-produced analysis |
| `GET /api/audit/reviews/history/{brand}` | `{records,next_cursor}`; `limit` 1–100, optional `cursor` |
| `GET /api/audit/reviews/{run}` | Metadata, current decision, revision and ordered events |
| `GET /api/audit/reviews/{run}/snapshot` | `{analysis,configuration}` using the encrypted evaluated snapshot |
| `POST /api/audit/reviews/{run}/decision` | `{decision,expected_revision}` plus request key; original/created `AuditEvent` |
| `DELETE /api/audit/reviews/{run}` | Admin only; idempotent 204 |
| `GET /api/audit/analytics/{brand}` | Schema 1.0 totals, outcomes, categories, top 100 rule/version counts and daily UTC rows |

Analytics accepts `days=1..90` (default 30, server clock), or explicit timezone-aware `start`/`end` of at most 90 days ending no later than server now. Explicit periods use `[start,end)` and are converted to UTC.

The denominator is all completed, unexpired, undeleted authenticated analyses evaluated in that period. Pending means no human decision; outcomes use the latest decision **now** for the cohort, and event count includes all its decision events. Failed/in-progress extractions, legacy/shared runs and static visual-only checks are excluded. Category/rule counts use validated findings, not real-world correctness or ROI. No fabricated percentage or compliance score is shown. One aggregation feeds all facets from the same selected input; results are majority-read, not a historical transaction snapshot at `generated_at`. `generated_at` indicates response freshness. Empty cohorts return zero totals and all four zero outcome buckets. History paging never changes aggregate totals. The dashboard explicitly labels its period, UTC timezone, update time and excluded data; history itself lists all retained dates.

## Verification

`backend/tests/test_audit.py` has offline security tests and real local MongoDB tests; database tests intentionally skip unless `PRAMANA_TEST_MONGODB_URI` explicitly targets localhost. Each test creates and drops only its own randomized test database. Backup/restart tests additionally require `PRAMANA_TEST_MONGO_CONTAINER` naming a disposable local test container.

Example verification environment (use an unused port/container name):

```powershell
docker run --detach --name pramana-audit-verification --publish 127.0.0.1:27028:27017 mongo:8.0 --bind_ip_all
$env:PRAMANA_TEST_MONGODB_URI='mongodb://127.0.0.1:27028'
$env:PRAMANA_TEST_MONGO_CONTAINER='pramana-audit-verification'
$env:REQUIRE_REAL_OCR='1'
uv run --locked python -m pytest --tb=short
uv run --locked python -m compileall -q backend scripts
Set-Location frontend
npm.cmd run build
npm.cmd run lint
```

The tests exercise real encrypted review/receipt/configuration replay; app and database restart; actual `mongodump`/`mongorestore` into a different database; duplicate analysis/decision races; competing reviewer conflicts; role/organization isolation; category/outcome/day reconciliation; history paging; expiry filtering; deletion; event caps; safe failures; and confirmed PDF evidence surviving removal of extraction state. They do not contact Atlas or alter a deployed application. Delete only your disposable verification container when done.

Actual Windows results on 3 November 2026:

| Check | Result |
|---|---|
| Full backend suite with local MongoDB/container variables and `REQUIRE_REAL_OCR=1` | 187 passed, 1 existing warning, 86.69 s |
| Final `uv run --locked python -m pytest backend/tests/test_audit.py --tb=short` with local MongoDB/container variables | 14 passed, 1 existing warning, 18.32 s; real restart and backup/restore included, no skips |
| `uv run --locked python -m compileall -q backend scripts` | Passed after final backend changes |
| Final `npm.cmd run build` | Passed: TypeScript and Vite production bundle |
| Final `npm.cmd run lint` | Exit 0; only the two existing React-effect warnings in AuditTrailPage and BrandGuidelinesPage |
| `git diff --check` | Passed; only LF/CRLF conversion notices |

The full run preceded the final audit error-contract separation and credential-generator test; the final 14-test audit run checked those additions. The pytest warning is the existing Starlette/httpx TestClient deprecation. Tests used a disposable loopback-only MongoDB 8.0 container, not Atlas; its database data/anonymous volumes were removed after verification. The browser automation host was unavailable, so interactive customer journeys remain unverified; frontend TypeScript/build/lint and direct real-database API flows were checked. No hosted deployment or production backup/restore was performed.

References checked: [MongoDB atomic writes and conditional filters](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/), [cryptography authenticated encryption](https://cryptography.io/en/latest/hazmat/primitives/aead/).
