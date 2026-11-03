# Optional retained storage

This local revision removes account setup. Do not follow historical access-key or Firebase instructions. The current app uses a shared workspace; all visitors can access new retained reviews and originals. Historical private collections remain separate. See [audit configuration and boundaries](audit-and-analytics.md).

No hosting, cloud configuration or private environment files were changed or verified as part of this revision. Existing provider settings and old deployment notes are not proof of current hosted behavior.

## Backend settings

For retained snapshots configure `MONGODB_URI`, `MONGODB_DB`, `PRAMANA_AUDIT_KEYS`, `PRAMANA_AUDIT_ACTIVE_KEY` and optionally `PRAMANA_AUDIT_RETENTION_DAYS`. Keep existing encryption keys. `PRAMANA_REQUIRE_MONGODB=1` and `PRAMANA_REQUIRE_AUDIT=1` enforce configured storage rather than temporary storage.

Optional original retention uses existing `BUNNY_STORAGE_HOST`, `BUNNY_STORAGE_ZONE` and `BUNNY_STORAGE_PASSWORD`; these belong only on the backend. The host is a hostname, not a URL; use the private zone's storage password. `PRAMANA_REQUIRE_BUNNY=1` enforces this configuration. A private storage zone prevents direct provider downloads; shared API downloads remain public by product design.

`CORS_ORIGINS` contains exact browser origins; `VITE_API_BASE_URL` points to the API. No cookies or identity credentials are sent. Preserve private files and never put storage/encryption credentials in VITE variables or source control.

## Verification before any separately authorized deployment

Check `/health` and `/ready`, then use fictional content to analyze, inspect evidence, explicitly decide, and reopen the same retained review after restart. Verify metadata mode and retained mode separately. `scripts/check_audit_deployment.py` writes and removes only its fictional check record through the operator repository; run it only against an authorized target. The original transport can be simulated with its existing option. Real Bunny transport, backups, restore, monitoring and deployed end-to-end behavior require independent verification.

The repository's deployment manifests are preparation only. No push, deployment, hosting change or provider action is authorized by this document.
