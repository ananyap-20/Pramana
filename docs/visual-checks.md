# Visual brand and accessibility checks

The Visual Checks tab supports `rendered` and `static_declarations` measurements. Both preserve exact input hashes, draft/version labels, configured source/version/excerpt and manifest digest. Neither approves or publishes content. The bounded renderer completes the originally missing rendered-output path; this is not a general visual-brand recognizer or full WCAG audit.

## Run and configure

```powershell
uv sync --locked --all-groups
uv run playwright install chromium
```

On Linux, install the runtime dependencies with `uv run playwright install --with-deps --only-shell chromium`. The Dockerfile includes browser installation; this revision did not build or deploy the container. `PLAYWRIGHT_BROWSERS_PATH` may point to a protected operator-owned runtime directory. Missing Chromium returns an explicit 503 rather than silently substituting static results.

The existing fictional LumaDesk brand includes a versioned sample policy and a small fictional sample PNG. Use **Load fictional sample** to exercise logo, colors, contrast and alt checks. The sample is not Pramana's logo and does not approve a real organization's identity. `PRAMANA_VISUAL_MANIFEST_PATH` overrides the sample with an operator-managed JSON policy, never a draft-provided path. Missing/inactive/unapproved or wrong-brand policies return 404; malformed configured policies fail startup. Policy and asset files are bounded and validated.

Manifest fields remain `brand_id`, `version`, `approved`, `active`, pinned `source_id`/`source_version`, `source_text`/`source_excerpt`, `logo_selectors`, `logo_sha256`, `palette`, and optional `text_exemptions`. See `backend/app/data/lumadesk-visual-demo.json` for the clearly fictional template. Replace every fictional field with verified real rules before using it for a real brand. Supported policy selectors are a tag, .class or #id. Exact source excerpts must exist in their configured source version.

## API and input boundaries

`POST /api/visual/analyze` accepts existing HTML/CSS/PNG/JPEG inputs plus `mode` (default `static_declarations` for compatibility), `viewport_width` (320-1920, default 1280) and `viewport_height` (240-1200, default 720). The UI selects rendered measurement by default and offers desktop/mobile viewports. `GET /api/visual/demo` returns only the bundled fictional sample when its demo policy is active.

Limits remain 100,000 HTML characters, 32,000 CSS characters, 8 single-frame PNG/JPEG assets, 192 KiB per base64-decoded asset, 384 KiB combined assets, 768 KiB request, 1,000 DOM nodes/results, 32 levels and a 2 MiB worker response. Every HTML image references a supplied `asset:ID`; there is no arbitrary URL input. Scripts, events, frames, external image links, duplicate/unsupported attributes and malformed nesting are rejected before rendering. Rendered CSS additionally rejects URL/font/import/namespace loads, escaped rules and reserved measurement attributes. Unknown or complex rendering effects cannot become a false pass.

Requests have bounded upload time and one concurrent visual worker. The static worker retains its 5-second deadline and Python I/O guard. Rendering has a hard 30-second parent deadline; Windows caps the entire process tree to 1 GiB and 16 processes (the OCR budget remains unchanged). Temporary browser profiles and descendants are removed at exit/deadline. Worker errors expose safe messages without draft content or provider credentials.

## Rendered measurements

A new nonpersistent Chromium instance/context uses the browser sandbox, JavaScript disabled, service workers blocked, no downloads, and a content security policy denying external content. The sole synthetic document navigation is fulfilled from supplied data; every other browser request is aborted. The browser receives only a minimal runtime environment without application credentials. Only an application-owned DevTools measurement function runs. Supplied HTML is never embedded into the reviewer UI.

Computed styles include the real browser cascade, inheritance, simple media queries, size/weight and element geometry. Solid transparent backgrounds/foregrounds are composited without threshold rounding. Gradients, image backgrounds, opacity, overlays, generated content, transforms, filters, masks/clipping, alternative text fill, animations and transitions return Indeterminate where their appearance cannot be established. Offscreen layout is measured at the recorded viewport; hover/focus/visited states, native accessibility behavior and all possible browser effects are not certified.

- Logo: exact PNG/JPEG SHA-256 against the policy. Recompression, altered/flattened marks, placement and subjective design quality remain human checks.
- Palette: only configured color/background roles. Photograph pixels are not scanned as brand violations.
- Contrast: computed colors/background chain, size, weight, unrounded ratio, threshold, element bounds and rule version. AA uses 4.5:1 normal text and 3:1 at 24px or 14pt bold (700+). Explicit hidden/inactive and approved decorative/logotype cases are identified. See [W3C's contrast explanation](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- Alt text: exact supplied image attributes and interactive ancestry. Missing alt is flagged; an explicit empty decorative alt is distinguished. Presence never proves description quality.

Rendered responses include Chromium version, viewport, script/request restrictions and `mode: rendered`. Static responses retain their original declaration-only scope and `mode: static_declarations`. Four existing evidence states are the only finding states. Input, source and manifest hashes remain available for replay; visual results are temporary and separate from content-review decisions.

## Verification and isolation limits

Real Chromium fixtures cover inheritance/cascade/media, exact logo/alt, near-threshold normal/large contrast, compositing, geometry, harmful HTML/CSS, unsupported effects, original input/version hashes and actual deadline handling. Browser acceptance submits real visual requests through the production UI. See [the current acceptance report](mandatory-feature-verification.md).

Browser sandboxing, request blocking, input validation and process/resource limits are defense layers, not proof against every native browser vulnerability or a certification of OS-wide filesystem/network confinement. Production OS/container controls and a deployed Linux/browser smoke test remain deployment responsibilities. No draft is sent to an external AI service.
