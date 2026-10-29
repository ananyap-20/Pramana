# Proposed Round 3 improvements

These are proposals, not implemented features. Estimates assume one engineer familiar with the current code and exclude external review time.

## 1. Richer document and image intake

- **Problem:** Current inputs are pasted text or ordinary paragraphs from `.docx`; many campaign files contain PDFs, images, tables, or visual text.
- **User value:** Reviewers can start from the assets they already receive and see when extraction is incomplete.
- **Approach:** Add a separate intake pipeline for PDF and image files. Preserve page/region coordinates when available, expose extracted text and extraction confidence, and require human confirmation when OCR confidence is low. Feed only confirmed extracted text into existing rules; do not weaken the evidence validator.
- **Effort:** Medium, about 5–8 engineering days for one format and a small end-to-end path; additional formats need separate estimates.
- **Dependencies and risks:** Select and pin an extraction/OCR library; test licenses and deployment memory/CPU. Scanned text, tables, and poor image quality can create omissions or false confidence. Bound compressed and expanded file sizes and page counts.
- **Success measure:** On a labeled, fictional document set, at least 95% of expected paragraphs are extracted for supported text PDFs; low-confidence OCR is visibly marked and never treated as a verified passage without review.

## 2. Visual brand and accessibility checks

- **Problem:** Text rules do not detect unapproved logos, color use, typography, contrast, or missing image descriptions.
- **User value:** Review can include common web and campaign visual standards and make accessibility issues actionable.
- **Approach:** Start with deterministic checks for supplied brand colors, approved logo assets, and rendered text contrast, plus a check for missing alt text in HTML. Return the measured element/value and the relevant configured rule. Keep subjective layout/style judgments as human review.
- **Effort:** Medium, about 4–7 engineering days for a narrow HTML/image path.
- **Dependencies and risks:** Need an approved asset/palette source and a controlled rendering engine. Dynamic content, image compression, and font rendering can change measurements; contrast standards must be chosen and cited.
- **Success measure:** On a labeled fixture suite, report zero unexplained misses across the supported exact logo/color/contrast checks, and provide a reproducible measurement in every finding.

## 3. Review analytics and persistent audit history

- **Problem:** Current history is shared process memory, stores only latest 100 summaries, and disappears when the service restarts. It cannot support durable trend analysis.
- **User value:** Teams can identify recurring issues and see how human review outcomes change over time.
- **Approach:** First define retention and access policy; then add authenticated organization/user identity and a relational store (PostgreSQL) with append-only review events. Build category counts from persisted events with clear time windows and denominators. Avoid retaining draft text by default; if text retention is needed, require an explicit policy and controls.
- **Effort:** Large, about 8–12 engineering days for an authenticated single-organization foundation and basic analytics, excluding operational setup.
- **Dependencies and risks:** Identity/authentication, database provisioning and backups, privacy review, migrations, retention/deletion workflows, tenant isolation, and cost monitoring. A “free” database tier may expire or change; verify current terms before choosing a provider.
- **Success measure:** A review and its decisions survive a restart; access-control tests prevent cross-organization reads/writes; aggregate counts reconcile with source events for a documented period.

## Order

1. Add document intake with explicit confidence and safe limits.
2. Add a small set of measurable visual/accessibility checks.
3. Build persistence and authorization before presenting analytics as organization-wide or audit-grade.
