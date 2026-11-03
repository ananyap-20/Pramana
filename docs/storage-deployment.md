# MongoDB and Bunny deployment

## Verified on 3 November 2026

The real MongoDB connection passed the metadata write/decision/reconnect check. The authenticated API also saved encrypted evidence and a decision, reopened the application with a new database client, retrieved both, rejected anonymous access and deleted only its fictional check record. This verifies local API access to Atlas, not the hosted Render connection.

The hosted API `/health` currently reports `in_memory_demo_not_durable`. Render must receive the MongoDB and audit settings before the public website uses durable storage. No Bunny account exists yet, so no live Bunny upload or download has been verified. Provider credentials were never printed.

## Private configuration already prepared

`.env.audit` holds newly generated organization identities and encryption keys; `.env.audit.access-key` holds the separate administrator access key for the website. `.env.render` combines MongoDB/audit settings for the Render backend's **Environment → Add from .env** form. These files are ignored by Git. Never put them in the frontend, screenshots, chat, or a commit. Preserve a protected backup of the audit encryption keys: losing them makes retained evidence unreadable.

## Connect the existing Render service

1. Open **pramana-api → Connect → Outbound** and copy the IP ranges. In Atlas, allow those exact ranges under **Network Access**; use a database user restricted to the `pramana` database. Do not open Atlas to the entire internet.
2. Open **pramana-api → Environment → Add from .env** and privately import the contents of `.env.render`. It uses the observed frontend origin `https://pramana-frontend.onrender.com`. After connecting the custom domain, replace that origin with the final HTTPS origin.
3. Deploy the tested source changes to the same `codex/pdf-image-intake` branch watched by Render. Keep the existing Python runtime while PDF/image hosting remains deferred. No Docker runtime is needed just for MongoDB and Bunny HTTP storage.
4. Require `/health` to show `mongodb_review_metadata` and `/ready` to show `audit: true`.
5. On the frontend, connect the private access key from `.env.audit.access-key` using the existing organization-key control. Without it, protected deployments reject shared review endpoints. Never place this key in a `VITE_` variable.
6. Analyze fictional text, save a human decision, redeploy the backend, and verify the same review and decision remain. Confirm records in Atlas `audit_reviews_v1`. Back up and restore Atlas data and encryption keys before relying on production recovery.

## Create and connect Bunny

1. Create a Bunny account and a **Storage zone**. Account terms/billing must be completed by the owner. Choose the region deliberately; charges are controlled by the provider, not this repository.
2. Keep the zone private: do not attach a public CDN Pull Zone. In its **Access** page obtain the hostname, zone name and Storage password. Use the zone password, not the account API key.
3. Save these privately in `.env.bunny`:

```dotenv
BUNNY_STORAGE_HOST=sg.storage.bunnycdn.com
BUNNY_STORAGE_ZONE=YOUR_ACTUAL_ZONE_NAME
BUNNY_STORAGE_PASSWORD=YOUR_ACTUAL_ZONE_PASSWORD
```

The hostname shown is Singapore's example; use the zone's real regional hostname from Access.

4. Add these three values to **pramana-api → Environment**, together with `PRAMANA_REQUIRE_BUNNY=1`, and redeploy. Do not add them to the frontend.
5. Run `uv run --env-file .env.bunny python scripts/check_bunny.py`. It uploads one encrypted fictional object, downloads/decrypts it and removes that exact object. Require PASS and successful cleanup.
6. Require `/ready` to show `private_files: true`. Analyze a fictional DOCX through the authenticated website. Confirm the review in MongoDB and an encrypted `.bin` in Bunny. The authenticated `GET /api/audit/reviews/{run_id}/original` returns the exact original as a download; another organization must get 404.
7. Restart the backend and retrieve the same original and review again. A real hosted restart/download journey remains required; transport unit tests alone do not prove provider integration.

## Storage behavior and operations

Confirmed audit DOCX reviews automatically retain their original. Confirmed PDF/image audit reviews use the same path when intake is enabled separately. Plain text evidence is encrypted in MongoDB. Unconfirmed uploads and previews remain temporary; no durable OCR queue is implemented here. The existing human confirmation/approval boundaries remain intact.

Originals are encrypted with AES-GCM before upload, bound to organization and review identifiers, limited to 5 MiB, and verified against SHA-256 after download. Bunny passwords stay server-side; transport permits only official regional Storage hostnames, validates object paths, disables redirects and bounds network timeouts/download sizes. Downloads require both authenticated organization access and an unexpired retained parent review. No public download links are issued. The independent cleanup entry point is `python scripts/cleanup_files.py`, with the same private backend environment. Schedule it on an always-on runner if the API can sleep; each run handles up to 100 expired objects.

MongoDB `audit_files_v1` records pending uploads before sending bytes. Failed uploads remain sweepable. Completed references share the review's expiry. There is intentionally no TTL index on file references: deleting them before deleting Bunny objects could leak retained files. A running API sweeps up to 100 expired references every minute, deleting each Bunny object before removing its reference. Failure retains references for retry and marks readiness unhealthy. An always-on service or independent cleanup runner is required for timely physical cleanup while Render is sleeping/offline. Logical access expires immediately even when provider deletion is pending. Administrator review deletion removes its original before removing the review.

`render.storage.yaml` is an opt-in complete configuration template, not applied to the running Blueprint. It requires MongoDB, audit and Bunny configuration; it fails startup on omissions. Its free compute is for a demo only and keeps OCR disabled. Do not create a duplicate Blueprint accidentally; update the existing Blueprint deliberately once required settings exist. Production requires an appropriately sized always-on host, backup/restore verification, monitoring, rate/capacity measurements and hosted access tests. OCR worker isolation remains a separate release gate.

Official Bunny transport contract: https://bunny.net/docs/storage/http (Storage password in AccessKey, regional HTTPS endpoints, binary PUT with uppercase SHA-256 checksum, GET, DELETE).
