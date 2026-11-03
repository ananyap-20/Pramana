# Static visual brand and accessibility checks

Implemented 3 November 2026. This is the safely verifiable portion of mandatory improvement 2, not completion of the isolated-renderer requirement in backend plan section 6. No renderer was added. No browser, script evaluation, URL fetching, external AI, publishing, rewriting or review-decision writes occur. Existing text and intake evidence validation remains unchanged.

## Setup and approval

No new dependencies. Install the existing locked environment with `uv sync --locked --all-groups`. An operator places a JSON manifest on the backend filesystem and sets `PRAMANA_VISUAL_MANIFEST_PATH` before startup. The path is server configuration, never accepted in an analysis request. At startup it is read once (64 KiB maximum), validated, and held as a snapshot. Missing configuration, wrong brand, inactive or unapproved configuration returns 404. Invalid configured files fail startup. One brand manifest per application instance is supported.

Example **fictional configuration template**, requiring actual human approval, real source text and real digest before use:

```json
{
  "brand_id": "example",
  "version": "visual-1",
  "approved": false,
  "active": false,
  "source_id": "brand-guide",
  "source_version": "1",
  "source_text": "Approved heading color is #123456.",
  "source_excerpt": "Approved heading color is #123456.",
  "logo_selectors": ["#logo"],
  "logo_sha256": [],
  "palette": [{"selector": ".heading", "property": "color", "colors": ["#123456"]}],
  "text_exemptions": []
}
```

Populate `logo_sha256` with lowercase SHA-256 digests of approved PNG/JPEG bytes. The source excerpt must exist verbatim in its pinned source text. This integrity check does not prove the source or a finding correct; the operator must verify actual configuration against the approved source. Optional `text_exemptions` contain `selector` and `reason` (`logotype` or `pure_decoration`) and require that same human verification. Request HTML cannot declare its own brand approval or contrast exemptions.

## API contract

`POST /api/visual/analyze`, JSON body; also described in FastAPI `/docs` and `/openapi.json`:

```json
{
  "brand_id": "example",
  "draft_id": "draft-123",
  "draft_version": "v2",
  "html": "<p class=\"heading\" style=\"color:#123456;background-color:#fff;font-size:16px;font-weight:400\">Hello</p>",
  "css": "",
  "assets": []
}
```

Images use `<img id="logo" src="asset:logo-file" alt="Example logo">` and an asset entry `{"asset_id":"logo-file","media_type":"image/png","content_base64":"..."}`. Assets are supplied bytes, not URLs or filesystem paths. Every HTML image must reference one valid supplied asset. Upload does not approve an asset: only the server manifest can establish an exact logo digest match. Photographs may be uploaded but their pixels are not subjected to palette rules.

The response is `VisualResponse`, with:

- `schema_version: "1.0"`, `mode: "static_declarations"`;
- supplied `brand_id`, `draft_id`, `draft_version`, `input_sha256`, `assets_sha256`;
- `manifest_version`, `manifest_sha256`, pinned `source_id`, `source_version`, exact `source_excerpt`;
- `findings[]`: `check`, `rule_version`, `element`, `evidence_status`, `result`, `explanation`, `evidence`;
- explicit `limitations[]`.

Element references are deterministic one-based `node:N:tag` start-tag positions in the passive parser, not browser DOM selectors. `evidence.html_start_tag` is copied exactly from the submitted HTML. Absent configured targets instead use the manifest selector and `configured_target_absent`. Input integrity uses SHA-256 of `json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")`; exact HTML/CSS strings and submitted asset bytes/base64 are bound to the caller's draft/version. Nothing is durably retained: the caller must preserve the exact original request for replay. IDs are labels, not authenticated ownership.

Only the existing four evidence statuses are used: `Supported`, `Contradicted`, `Unsupported (needs verification)`, `Indeterminate (needs verification)`. Each result describes its narrow measurement; `Supported` is never approval of the page. No review decision is generated. Responses use `Cache-Control: no-store`.

Errors use `{"detail":"..."}`. Visual request validation is sanitized into a generic 422 message without reflecting submitted content. Statuses: 404 no approved configuration, 413 request size, 422 malformed/unsupported HTML or assets or analysis limits, 429 per-process capacity, 408 upload/worker deadline, 503 worker unavailable. No exception traceback, file path, draft text or credential is included in errors. Operators must retain immutable approved manifest/source versions for replay; `manifest_sha256` uses the same canonical JSON algorithm as the request hash.

## Supported measurements

**Logo:** exact bytes only on configured image selectors. `exact_digest_match` is an approved digest match; `digest_not_listed` means verification is needed, not proof of an unauthorized brand/logo. Resized/recompressed/recolored/flattened logos are not recognized. CSS distortion and placement are unmeasured.

**Palette:** only manifest `color` / `background-color` targets, matched by a single tag, `.class`, or `#id`. Normalize `#rgb`, `#rrggbb`, integer `rgb(r,g,b)`, `black`, `white`. Missing/unresolved colors are indeterminate. No photograph pixels are scanned. A mismatch contradicts the configured declaration rule only.

**Contrast:** text-bearing elements require explicit foreground, background, font-size and font-weight declarations on that element. Supported CSS uses simple selectors and inline declarations, ordered by ID/class/tag specificity then source order, with inline declarations last. Explicit size is px or pt; weight is normal/bold or 100..900 in steps of 100. Supported property grammar: color, background-color, font-size, font-weight, opacity, background-image, display, visibility. Unknown properties/syntax/selectors anywhere conservatively make color/contrast results indeterminate. No UA defaults or inheritance are invented.

Each contrast result includes foreground/background, font size in CSS px, weight, ratio, threshold, exemption, element and `WCAG-2.2-1.4.3-static-v1`. Opaque sRGB declared pairs use WCAG relative luminance, channel boundary 0.04045. Compare the unrounded ratio against 4.5, or 3 for >=24px / >=14pt bold (700+). Hidden attributes without a display override, disabled buttons and operator-configured logotype/pure-decoration text are explicit exemptions with a null ratio. `aria-hidden` alone is not a visual exemption. Unresolved gradients/images, alpha colors, ancestor opacity, unsupported compositing, relative units, missing declarations and CSS complexity yield indeterminate with null ratio. Explicit exemptions are recorded separately from measurement.

These are **declaration-level color-pair results**, not computed browser styles or rendered contrast certification. Layout/overlap, actual fonts and unusual font metrics, image text, browser repairs, hover/focus/visited/pseudo states, generated content, non-text contrast and full WCAG compliance remain unverified. A renderer with verified OS-level confinement is still required for the original rendered-output scope.

**Alt text:** meaningful `<img>` without a nonblank alt yields `missing_description`; nonempty alt yields `description_present_quality_unverified`. Explicit empty alt outside interactive ancestry recognizes declared decorative intent (`declared_decorative`). Conflicting presentation/ARIA labeling is indeterminate; interactive empty-alt images require review. Actual meaning/quality/intent, assistive-technology behavior and image contents are not inferred. Standalone uploaded images get no HTML alt finding.

## Bounds and isolation

768 KiB raw request including chunked bodies; 5-second upload deadline; one active request per application process (429 otherwise). HTML <=100,000 characters, CSS <=32,000; <=1,000 elements, depth <=32, <=32 attributes per element, <=2,048 characters per attribute. Explicit balanced passive HTML only. Scripts, event handlers, style elements, SVG, iframes, objects, embedded documents, processing instructions, external image references and non-fragment links are rejected. Supplied instructions remain inert text. CSS is parsed as strings and never executed or fetched; unsupported CSS returns uncertainty.

<=8 unique asset IDs; <=262,144 base64 characters per asset; <=384 KiB total decoded bytes; PNG/JPEG only, matching declared format, one frame, <=1 million pixels each, verified and decoded. SVG, animation, type spoofing and malformed files fail safely. No executable/embedded image behavior is interpreted.

Parsing/decoding runs in a disposable Python process: isolated import mode, explicit UTF-8, stripped inherited environment (no application/cloud secrets), 5-second hard parent deadline, Windows Job Object process-tree/memory bound or Unix resource limits, 256 MiB memory. <=1 MiB serialized worker input; <=1,000 findings; <=2 MiB output. Worker imports finish before a Python audit hook denies file opening, sockets, subprocesses and exec/spawn/system operations; analysis uses memory buffers only. Timed-out workers are killed/reaped and streams closed. No temporary draft files are written.

This is a defense around passive parsers, **not an OS network/filesystem security sandbox** against native-code exploitation. No renderer or untrusted executable is introduced. Shared/public production hosting still requires authenticated ownership, global admission/rate limits across workers, stronger OS confinement and deployment verification. The endpoint remains unavailable until an operator supplies a manifest.

## Verification

Fixtures are fictional and labeled in `backend/tests/test_visual_checks.py`: exact/unlisted logo bytes, target-only palette, normal/large near-threshold pairs, exact 14pt bold boundary, alpha/gradient/image/compositing uncertainty, exemptions, alt/decorative/interactive cases, invalid/oversized assets, malicious/ambiguous HTML, DOM/output bounds, no configuration/approval bypass, private response, real worker PNG/JPEG/Unicode, actual deadline and recovery, chunked admission limits and the real Python I/O guard. Fixture success establishes only the documented static scope, not general detection accuracy.

Windows verification on 3 November 2026:

| Command | Actual result |
|---|---|
| `$env:REQUIRE_REAL_OCR='1'; uv run --locked python -m pytest --tb=short` | 174 passed in 58.22 s; real OCR required |
| `uv run --locked python -m pytest backend/tests/test_visual_checks.py --tb=short` | Final targeted rerun after OpenAPI error-schema adjustment: 73 passed in 5.83 s |
| `uv run --locked python -m compileall -q backend` | Passed after final code changes |
| `git diff --check` | Passed; Git reported only existing LF/CRLF conversion notices |

Both pytest runs reported the existing Starlette/httpx TestClient deprecation warning. The complete run preceded only the final OpenAPI error-schema declaration/test adjustment; the final visual suite verified that adjustment. No Linux/container renderer, frontend integration, hosted deployment or full WCAG audit was performed. Existing uncommitted MongoDB/frontend work was preserved; no dependency, Git history or remote changes were made by this task.

Rules reference: [W3C WCAG 2.2 Understanding SC 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), reviewed 3 November 2026 (thresholds, large text, exemptions, relative luminance and unrounded comparisons).
