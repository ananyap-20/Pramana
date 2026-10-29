# Pramana agent rules

## Product boundaries

Pramana is a pre-publication brand-governance tool. Humans control review and approval. Never auto-publish or silently rewrite a draft. \`Unsupported (needs verification)\` is not a false claim.

## Architecture

Inspect the repository before editing and follow its established conventions. Prefer small, testable modules and separate repositories/configuration, rule execution, finding validation, and API serialization. Use React + TypeScript, FastAPI, and PostgreSQL only when consistent with the real setup; do not add dependencies or broad abstractions prematurely.

## Evidence integrity

Preserve the exact evaluated draft/version. A flagged quote must exist in that draft; a cited source and excerpt must exist in the permitted, active source version. A citation match alone does not prove a finding correct. Use only: \`Supported\`, \`Contradicted\`, \`Unsupported (needs verification)\`, and \`Indeterminate (needs verification)\`.

## Security and privacy

Never hardcode or commit credentials. Validate untrusted input. Do not send confidential drafts to external AI services without authorization. Avoid logging confidential drafts, credentials, or unnecessary personal data; apply access control and data separation when those features are introduced.

Treat uploaded documents as untrusted input. Accept only explicitly supported file types, enforce size limits, do not execute document macros or embedded instructions, and return safe extraction errors.

## Workflow

Inspect first; make small, reversible diffs; preserve existing behavior unless a change is justified. Run relevant checks after changes and report actual results. Update docs when setup changes. Ask before destructive, costly, externally visible, or materially architecture-changing actions. Do not claim completion without verification.

