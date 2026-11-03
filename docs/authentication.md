# Authentication and workspace access

Pramana now requires a validated Firebase identity for application features. The landing page combines a product introduction with email/password sign-in, signup, Google and GitHub, password reset and email-verification guidance. Missing configuration leaves authentication unavailable; there is no public-demo fallback. Authentication does not establish production readiness.

## Provider choice and cost

No suitable identity provider was configured in the inspected checkout. Firebase Authentication supports all three requested methods, a maintained JavaScript SDK and a Python Admin SDK for verified server session cookies. Password storage, email actions and OAuth transactions remain with Firebase; Pramana does not implement them itself. MongoDB remains the application's review/audit database. Installing the Firebase Admin SDK does not introduce Firestore application storage.

Official sources checked for this implementation:

- [Firebase session cookies](https://firebase.google.com/docs/auth/admin/manage-cookies): server-generated cookies, recent authentication, revocation checks and clearing client SDK state.
- [Email/password and enumeration protection](https://firebase.google.com/docs/auth/web/password-auth).
- [Google sign-in](https://firebase.google.com/docs/auth/web/google-signin) and [GitHub sign-in](https://firebase.google.com/docs/auth/web/github-auth).
- [Firebase quotas](https://firebase.google.com/docs/auth/limits): Spark email quotas currently list 1,000 verification emails/day and 150 reset emails/day; account creation is limited to 100/hour/IP. Identity Platform's instrumentless Spark limits include 3,000 Tier-1 daily active users.
- [Identity Platform pricing](https://cloud.google.com/identity-platform/pricing): email/social Tier-1 has a first 50,000 MAU no-cost band on the relevant paid usage plan, then usage-based charges. Do not confuse this with the instrumentless daily cap. Terms and quotas can change. No billing account, paid resources or project settings were created or changed.

## Session architecture

1. The Firebase JS SDK handles email/password and Google/GitHub OAuth. Normal sign-in uses in-memory persistence. Redirect sign-in temporarily uses tab-scoped persistence for the SDK's own transaction; after completion or failure it is cleared and returns to memory persistence. No provider refresh token or audit key is intentionally retained by Pramana after the exchange.
2. `/api/auth/session` accepts only an ID token, verifies it with the Admin SDK (`check_revoked=True`), requires a supported provider and verified email, and requires authentication in the last five minutes. It creates a five-day Firebase session cookie. Accounts with unverified email cannot use protected APIs, even if they bypass the UI.
3. The host-only `__Host-pramana_session` cookie is HttpOnly, Secure, Path=/ and SameSite=Lax. It has a fixed lifetime; there is no silent rolling refresh. Expiry requires sign-in again. Only loopback development can explicitly select non-Secure, differently named local cookies with `PRAMANA_COOKIE_SECURE=0`.
4. Every private request validates the cookie using `verify_session_cookie(..., check_revoked=True)`. Firebase validates RS256 signature, issuer, audience/project, expiry and subject; its supported verifier fetches/caches certificates for rotation. Revoked/deleted/disabled credentials fail closed. Certificate, network, credentials and provider failures return a generic 503. The emulator environment is explicitly rejected.
5. Unsafe requests require an exact allowlisted `Origin` and an unpredictable CSRF nonce in both a host-only HttpOnly cookie and `X-CSRF-Token`. `/api/auth/csrf` returns the nonce to the allowed frontend; it is not an identity credential. CORS allows credentials only for exact configured origins, never `*`. Responses are no-store. Preflight does not grant application access.
6. Sign-out removes this browser's cookie and asks Firebase to revoke that account's refresh tokens/session cookies, affecting its other sessions too. If remote revocation is unavailable, the response states that limitation and still deletes the local cookie when the API is reached. If the API itself is unreachable, the UI clears local state but cannot promise the HttpOnly cookie was deleted: retry sign-out before leaving a shared device.

The frontend restores its identity from the server, gates every hash route, checks expiry/visibility and periodically revalidates. Logout and account/workspace changes clear the cached review and extraction capabilities. In-flight results from a previous session are discarded. Private responses identify their server-derived actor/workspace so a stale tab cannot render another cookie owner's response. Back navigation never bypasses the gate.

## Ownership and roles

Only Firebase's validated project + UID determines the actor. Email, email domain, browser-supplied roles, organization IDs and Firebase custom role claims do not grant application membership.

- A new UID receives a deterministic, isolated `p_…` personal workspace with reviewer permissions. It receives no existing organization's access and no administrator privileges.
- `PRAMANA_IDENTITY_MEMBERSHIPS` is a private server configuration list of `{ "uid": "verified-provider-uid", "organization_id": "org_team", "role": "reader|reviewer|admin" }`. The application supports one assigned organization per UID in this minimal model. There is no invitation, organization creation, workspace switcher or self-service role editor.
- Explicit members of the same organization may read its retained reviews/evidence. Readers cannot mutate reviews, upload/confirm/cancel extractions, run visual analysis or delete records. Reviewers can analyze and record human decisions; admins can additionally delete organization reviews. Membership changes require updating the server configuration and restarting the service; each request derives current permissions from that mapping.
- Extraction jobs bind an immutable owner actor at creation. All status, version, preview, original, confirmation, cancellation and analysis lookups require that owner **and** the temporary capability token. Organization membership does not transfer another user's temporary extraction. File capabilities remain an additional protection, never a substitute for identity. Authenticated transcription provenance records the confirming actor; confirmation is separate from content approval.
- Saved reviews use the existing organization-scoped encrypted repository and retention rules. Originals require authorization against the parent review before the storage lookup. Raw Bunny keys/URLs are not returned. Static visual analysis is stateless and is returned only to the requesting authenticated reviewer; it is not saved in audit analytics.

## Legacy separation and public exceptions

New identity flows use `identity_reviews_v1` and `identity_files_v1`. They do not expose legacy `audit_reviews_v1`, `audit_files_v1` or shared demo history. When private storage is configured, bounded operator/background cleanup continues to remove expired originals from both file namespaces; it does not grant users access to legacy records. Preserve existing legacy MongoDB TTL indexes and encryption keys until the operator has completed retention/migration review. Old operator-issued keys cannot bypass the outer identity boundary and are no longer the normal login. Authenticated `/api/reviews/*` legacy paths and capability-only intake review/analyze routes return 410; the frontend always uses `/api/audit` for saved analyses and human decisions. Existing engine/repository implementations remain for compatibility and historical verification, not public access.

The only unauthenticated HTTP exceptions are GET `/health`, `/ready`, `/api/auth/config`, `/api/auth/csrf`, `/api/auth/session` (returns only a verified current session or 401), and POST `/api/auth/session` and `/api/auth/logout` (both origin/CSRF protected). Exact-origin CORS preflight is also handled publicly. API docs/schema require identity. WebSocket upgrades are denied. Health/readiness return infrastructure status, not draft data.

No migration is automatic. An operator must inventory legacy namespaces, retention, encryption keys, record ownership and original references; obtain explicit authorization; back up and dry-run a separately reviewed migration preserving exact snapshots, hashes, source versions and events. A UID/email match alone is not authorization. This implementation supplies no migration command.

## Account collision, abuse and browser security

**Required provider setting:** allow multiple accounts per email address (disable “link accounts that use the same email”). This prevents Firebase's trusted-provider email matching from merging separate provider accounts. The app performs no `linkWithCredential`, email-based merge or provider discovery. Google, GitHub and password accounts with the same email may therefore have different UIDs and separate workspaces. Users should retain their original method. Linking is unsupported; any future linking needs verified explicit control of both accounts. A provider collision produces guidance, never a merge. This console setting must be checked against real provider configuration before release.

Enable Firebase email-enumeration protection, require a strong password policy, and review project signup/email quotas and abuse protections. UI login/signup errors are generic; password-reset UI says “if an eligible account exists.” Provider behavior and timing can still reveal information, so client messaging alone is not a guarantee. The API bounds auth bodies to 16 KiB, imposes a deadline, and limits exchanges/logout to 20 attempts/minute/client IP per process with a bounded table. Multi-instance deployments need additional shared edge rate limiting. Trust forwarded IP headers only from your known ingress, never arbitrary clients.

OAuth authorization, state and SDK redirect transaction security remain with Firebase's supported browser resolver. Google/GitHub use the provider's configured handler; the application accepts no client-supplied callback, return URL or `continueUrl`. Authorized domains, provider callback allowlists and Firebase's OAuth credentials must be configured narrowly. Normal login uses popups; redirects are an explicit alternative and need Firebase's documented redirect-domain setup for browsers that restrict cross-origin storage. Do not claim every provider flow uses PKCE when the provider SDK manages its own supported mechanism.

React escapes displayed text; uploaded/visual HTML remains inert and is never inserted into the document. No password, ID token, cookie, private draft or service-account credential should be logged. Keep access logs free of body/header dumps and query-string credentials. Configure HTTPS and deployment security headers, including a CSP restricted to the exact frontend/API and necessary Firebase handler/Google endpoints, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, `X-Content-Type-Options: nosniff` and a restrictive referrer policy. CSP endpoint allowlists depend on the selected auth domain; validate popup and iframe behavior after tightening them. An XSS flaw on a trusted origin could still act with the user's session; HttpOnly cookies do not remove that risk.

## One-time configuration checklist

1. **Firebase project/web app:** choose a project with Authentication, register a Web app and enable Email/Password, Google and GitHub. No phone/SMS is needed. Select multiple accounts per email, enable email enumeration protection and a required password policy. Set verification/reset email templates, support details and your approved continue URL; Firebase-hosted email action handlers process the links. App access requires verified email for every method.
2. **OAuth and domains:** enable Google and its support email; use your own production Google OAuth configuration/consent screen as required. Create a GitHub OAuth App, set its homepage to your frontend and its callback to `https://<authDomain>/__/auth/handler`, then enter its client ID/secret in Firebase only. Use the handler shown by Firebase for Google as well. Add only the frontend/auth domains and the local development domain you actually use to Firebase Authorized domains (localhost is not always pre-added). Do not add arbitrary previews or wildcard callbacks. For redirect mode, follow [Firebase redirect best practices](https://firebase.google.com/docs/auth/web/redirect-best-practices) for a same-domain handler/proxy or a supported custom auth domain.
3. **Backend secrets/settings:** set `PRAMANA_FIREBASE_PROJECT_ID`, Firebase Admin Application Default Credentials (prefer hosting workload identity where available, otherwise a mounted private service-account secret file referenced by `GOOGLE_APPLICATION_CREDENTIALS`), `MONGODB_URI`, `MONGODB_DB`, existing `PRAMANA_AUDIT_KEYS`, `PRAMANA_AUDIT_ACTIVE_KEY`, retention and optional Bunny settings. Grant only the permissions required for Firebase Auth verification/session management. Never commit the service account or put it in a `VITE_*` variable. Keep Secure cookies on in hosting.
4. **Frontend build configuration:** copy `frontend/.env.example` to an ignored `.env.local` and set its public `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` and `VITE_API_BASE_URL`. Both project IDs must match. Restrict the web API key appropriately for the Firebase APIs; it is public configuration, not an Admin secret.
5. **Hosting topology:** use same-site HTTPS domains (for example `app.example.com` and `api.example.com`) or route the API through a same-origin reverse proxy. Unrelated `vercel.app` / `onrender.com` domains cannot use these SameSite=Lax cookies. Set exact frontend `CORS_ORIGINS`, add no trailing slash, and configure TLS, CSP and trusted ingress/edge rate limiting. Do not weaken cookies to work around third-party-cookie blocking.
6. **Administrator bootstrap:** create and verify the intended administrator's account through the ordinary sign-up/provider flow; independently confirm its exact UID in Firebase Console. Privately add `[{"uid":"<confirmed UID>","organization_id":"org_your_team","role":"admin"}]` to `PRAMANA_IDENTITY_MEMBERSHIPS`, preserve any existing entries, and restart the API. Add future verified UIDs explicitly as reader/reviewer/admin. Never choose members by email domain. This grants access only to the new identity collection; legacy migration remains separate.
7. **Release integration checks:** with disposable real accounts, verify email delivery/verification, reset, all three sign-in methods, cancellation and redirect recovery, reload/back/expiry, logout/revocation across tabs, two-user/organization/role isolation, direct API attempts, document confirmation/evidence/decision/history, and retained originals/restart recovery. Google/GitHub and hosted email are blocked on configuration until these checks actually run. No push or deployment is part of this implementation.

## Local commands and verification scope

```powershell
uv sync --locked --all-groups
# Privately configure backend .env and frontend .env.local using the checklist.
# Local-only backend setting: PRAMANA_COOKIE_SECURE=0; use 127.0.0.1 consistently.
uv run uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
# In frontend/:
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
npm.cmd run test
npm.cmd run build
npm.cmd run lint
# From root:
uv run python -m pytest --tb=short
```

`test_identity.py` exercises the real HTTP identity/CSRF boundary and actual encrypted audit repositories with a local Mongo test double and a fake identity provider. It also uses real RSA-signed tokens with the Firebase verifier and replaces only certificate transport to check issuer, audience, expiry, signature, rotation and failure. `test_identity_intake.py` exercises actual PDF/OCR confirmation and audit decisions through that boundary. Historical backend modules test their original inner APIs via a test-only monkeypatch; no runtime setting disables authentication. Existing real Mongo acceptance checks require `PRAMANA_TEST_MONGODB_URI` pointing only to a disposable local database. Test doubles do not verify live Firebase, Atlas transactions/durability, Bunny or hosted mail/OAuth.

### Actual local verification — 3 November 2026

| Check | Actual result |
| --- | --- |
| Full backend suite using the project interpreter | 222 passed, 11 skipped before the final bounded legacy-cleanup addition |
| Final focused identity/audit/private-storage checks | 46 passed, 11 skipped; includes legacy-file expiry isolation |
| Frontend tests | 26 passed, including signup/verification, SDK persistence/redirect cleanup, cookie/CSRF exchange, invalid sessions, no public fallback, account changes and delayed-response isolation |
| Frontend production build and lint | Passed |
| Dependency audit after compatible gRPC transitive override | 0 reported vulnerabilities |
| PDF workflow | Actual text/scanned/mixed PDF extraction, preview, confirmation, identity-bound provenance and human decision tests passed with local OCR |
| Browser | Local landing page rendered in Brave; accessibility content and one narrow-window screenshot inspected. Further input was interrupted by user activity, then the dedicated window was closed. Full desktop/mobile visual and interactive verification remains incomplete. |
| Live Firebase, OAuth, hosted mail, Atlas and Bunny | Not tested against real configuration by this authentication work. The 11 skipped backend checks require a disposable real MongoDB. |

The sandbox denied loading the native Python dependencies. Authorized local verification ran through `.venv/Scripts/python.exe`; a preliminary system-Python run could not launch isolated workers with the correct packages and failed. Re-running with the project interpreter produced the passing workflow results above. No provider account settings, paid resources, live credential configuration, push or deployment was performed.
