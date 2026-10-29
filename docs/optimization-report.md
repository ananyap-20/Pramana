# Implementation and architecture notes

Snapshot verified 2026-10-29. The supplied source archive contained a React/Vite interface and FastAPI backend, but the README and reviewer/history screens overstated or simulated parts of the experience. This note describes the checked source after the local fixes.

## Current request path

1. The browser submits pasted text or a `.docx` file to FastAPI.
2. The service loads seeded fictional LumaDesk v1 rules and sources.
3. Four deterministic checks create candidate findings.
4. The finding validator verifies each quote against the evaluated draft and each rule/source/excerpt against active approved configuration. Invalid candidates are dropped.
5. The response includes exact evaluated text and validated Evidence Receipts.
6. A reviewer can record `approved`, `revision`, or `rejected`. History returns run ID, time, finding count, and decision events.

## Changes made in this pass

- Fixed the TypeScript build failure caused by parameter properties in an ES decorator class.
- Connected reviewer decisions and history UI to backend APIs; removed simulated reviewer names, fake cryptographic signing, fake approvals, and sample reanalysis from the history page.
- Kept the exact current draft available to the browser review/receipt flow and exposed matching context and character range. The backend history repository stores no draft or receipt passages.
- Added bounded in-process history (latest 100 records) with finding counts and timestamped decisions.
- Tightened missing-disclaimer candidate checks and explanation/action validation.
- Limited `.docx` uploads by compressed bytes, archive entries, expanded size, and extracted characters.
- Improved responsive navigation and removed externally fetched font assets.
- Updated README, evaluation, report, diagram, deployment config, and test documentation to match verified behavior.

## Verified snapshot

- Backend: 54 tests passed; one Starlette/httpx deprecation warning.
- Python: `compileall` passed.
- Frontend: `npm run build` passed.
- Browser journey: submit sample -> inspect receipts -> record a human decision -> see the same run and decision in history. Local browser/API evidence is recorded in [`test-matrix.md`](test-matrix.md).

## Material limitations

- No authentication, authorization, organization isolation, or rate limiting. A public user can submit drafts, read shared history summaries, and change a decision if they know its run ID.
- History is shared process memory, limited to latest 100 records, and lost on restart/redeploy/spin-down. It is not an immutable or durable audit log.
- Exact draft is returned to the submitting browser; it is not retained in backend history. Do not submit confidential copy to a public instance.
- Only ordinary DOCX paragraphs and pasted text are supported; there is no PDF, image, table, OCR, or general-purpose fact verification.
- No LLM was added. External draft processing would add cost, privacy, and evidence-grounding concerns; it is not needed for this verified deterministic demo.
- The source archive's Git remote points to `teclium28-jpg/Pramana`, while the request names `ananyap-20`. The repository identity needs user review before publishing.

## Architecture sketch

```text
React + TypeScript + Vite
  -> FastAPI input / response schemas
  -> Review service
  -> deterministic rule engine
  -> evidence/finding validator
  -> exact-draft receipts returned to browser
  -> in-memory metadata + human decision history (latest 100)
```

See [`pramana_workflow.svg`](pramana_workflow.svg) for the user-facing flow and [`round3-roadmap.md`](round3-roadmap.md) for proposed next work.
