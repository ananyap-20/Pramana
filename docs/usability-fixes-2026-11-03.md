# Review usability and PDF follow-up

The review screen now uses a reading column separated by dividers, with one finding open at a time and a distinct decision area beside it on desktop. Quotes, suggestions and provenance remain available without nested cards. On small screens, the decision area follows the reading column. Long reviewer IDs wrap within the decision history. Plain-text reviews no longer show the retained-original download control.

A six-step first-visit tour highlights the actual studio controls and navigation. It supports Back, Next, Escape and Skip; dismissal is stored in browser local storage, and the header Walkthrough control replays it. The tour does not edit a draft, run analysis or record decisions. The Guide remains available for reference.

Verified in the browser at desktop and mobile widths: tour navigation/completion/replay/Escape, persistence across reload, single expanded finding, no horizontal document overflow, a scanned PDF through OCR/preview/confirmation/analysis and a human revision decision. The localhost test server used only fictional identities and an in-memory MongoDB double, with real application middleware and extraction workers. Browser console contained no errors during these journeys.

Frontend build, lint and 14 API-client tests passed. The full backend suite completed without failures, with optional external integration cases skipped. New signed-in PDF acceptance tests cover text-only, scanned and mixed PDFs, a missing-CSRF rejection and cross-user extraction isolation. See `pdf-image-intake.md` for setup and deployment boundaries. No commit, push or deployment was performed.
