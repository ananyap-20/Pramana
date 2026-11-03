# Pramana frontend

This React/TypeScript/Vite app is the browser interface for the Pramana demo. For full architecture, backend setup, security limits, and deployment instructions, see the [project README](../README.md).

From this directory:

```powershell
npm ci
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Create a production build with `npm run build`. The hosted app reads `VITE_API_BASE_URL` at build time; set it to the deployed API origin before building. This value is public browser configuration, not a secret.

The warm editorial interface adapts the supplied HTML references to the existing application. See [design integration and verification](../docs/frontend-redesign.md) for the reference inventory, API mapping, unavailable features and browser verification limits.

Run `npm.cmd run test` for focused API-client/evidence regressions (Node 24 used), `npm.cmd run build` for TypeScript and the production bundle, and `npm.cmd run lint` for lint checks. Tests use Node's built-in runner; no additional packages are required.

Reviewer access is at `#/reviewer-access` and uses an administrator-issued organization key. Static visual checks are at `#/visual-checks` and require an approved backend manifest. Shared demo history retains metadata only; connected organization history can reopen saved snapshots. Original-file downloads depend on private-storage configuration. Existing draft, review, evidence, history and policy hash routes remain supported.
