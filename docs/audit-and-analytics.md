# Shared retained audit and analytics

The application opens without credentials. Retained audit is optional storage, not an access gate. All visitors can inspect new shared reviews, snapshots and configured retained originals. Use fictional, non-sensitive content. Anonymous decision events identify `anonymous_reviewer`, which is not a verified human identity.

## Configuration

Supply private `MONGODB_URI`, `MONGODB_DB`, `PRAMANA_AUDIT_KEYS` (key ID to base64 32-byte key) and `PRAMANA_AUDIT_ACTIVE_KEY`. Optional `PRAMANA_AUDIT_RETENTION_DAYS` is 1-90, default 30. `python scripts/create_audit_credentials.py` creates encryption settings exclusively in a new ignored `.env.audit`; it prints no secrets and never overwrites an existing file. No user access key is created. Preserve existing encryption keys and protected backups.

Missing optional audit configuration leaves text/DOCX metadata mode functional. Partial encryption settings, missing MongoDB, or `PRAMANA_REQUIRE_AUDIT=1` without audit configuration fail startup. `/ready` reports `audit: true` when configured. The frontend selects the matching API automatically. No Firebase, membership, provider, cookie or session setup is used.

New audit records use `public_reviews_v1`, originals use `public_files_v1`, and the fixed storage partition is `public_workspace_v1`. Previous `audit_reviews_v1` and `identity_reviews_v1` records are not migrated or exposed. Historical original-file expiry cleanup remains enabled when storage is configured. This preserves data without making former private histories public.

## Integrity and retention

Existing AES-GCM snapshot encryption, exact draft/source/configuration versions, SHA-256 integrity checks, majority/journaled writes, retention bounds, paginated history and real analytics remain in use. Keep encryption keys separate from backups; retaining ciphertext without keys cannot recover evidence.

`POST /api/audit/reviews/analyze`, `/reviews/analyze-document` and `/intake/{id}/analyze` require an `Idempotency-Key` of 16-100 ASCII letters, digits, underscores or hyphens. Changed payloads under a reused key conflict. Confirmed intake additionally requires its per-file `X-Intake-Token`; these expiring capabilities are not accounts. Decisions require `expected_revision` and a new idempotency key. Competing decisions cannot silently replace earlier events. Decisions append and never approve claims automatically.

`GET /api/audit/reviews/history/{brand}`, `/reviews/{id}`, `/reviews/{id}/snapshot`, `/reviews/{id}/original` and `/analytics/{brand}` are public within the shared partition. Responses use no-store. Upload bodies, time and concurrency remain bounded. Public account/profile and administration routes have been removed. Deletion is an operator repository operation; there is no anonymous destructive HTTP route.

Expiry is enforced on reads immediately; MongoDB TTL removes expired records asynchronously. Original deletion keeps retryable references on storage failure. Database operators remain responsible for protected backups, key custody and recovery. Application events are not a cryptographically immutable compliance certificate.

Real MongoDB integration can use a disposable native server via `PRAMANA_TEST_MONGOD`, with `PRAMANA_TEST_MONGO_TOOLS` for mongodump/mongorestore, or the existing local URI/container settings. Native tests now exercise actual database restart, backup/restore, retention, concurrency and analytics. Browser acceptance also restarts the API and reopens evidence and encrypted originals using a local object transport. See [the current verification report](mandatory-feature-verification.md). No hosted storage or Bunny-provider claim follows from these local checks.
