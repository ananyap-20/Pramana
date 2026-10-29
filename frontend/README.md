# Pramana frontend

This React/TypeScript/Vite app is the browser interface for the Pramana demo. For full architecture, backend setup, security limits, and deployment instructions, see the [project README](../README.md).

From this directory:

```powershell
npm ci
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Create a production build with `npm run build`. The hosted app reads `VITE_API_BASE_URL` at build time; set it to the deployed API origin before building. This value is public browser configuration, not a secret.
