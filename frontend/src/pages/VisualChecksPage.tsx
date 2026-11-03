import { useRef, useState, type FormEvent } from 'react'
import { analyzeVisual, ApiError, loadCurrentReview, type VisualAsset, type VisualResponse } from '../api/client'
import { EvidenceStatusBadge } from '../components/StatusBadge'
import { Icon } from '../components/Icon'

export function VisualChecksPage() {
  const [review] = useState(loadCurrentReview)
  const [html, setHtml] = useState('')
  const [css, setCss] = useState('')
  const [assets, setAssets] = useState<VisualAsset[]>([])
  const [result, setResult] = useState<VisualResponse | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reading, setReading] = useState(false)
  const submitting = useRef(false)
  const [standaloneId] = useState(() => crypto.randomUUID())

  async function readAssets(files: FileList | null) {
    setAssets([]); setResult(null); setError(''); setReading(true)
    try {
      const chosen = Array.from(files ?? [])
      if (chosen.length > 8 || chosen.some((file) => file.size > 192 * 1024) || chosen.reduce((n, file) => n + file.size, 0) > 384 * 1024) throw new Error('Use up to 8 PNG/JPEG assets, at most 192 KiB each and 384 KiB combined.')
      const loaded: VisualAsset[] = []
      for (const [index, file] of chosen.entries()) {
        if (file.type !== 'image/png' && file.type !== 'image/jpeg') throw new Error('Only PNG and JPEG assets are supported.')
        const bytes = new Uint8Array(await file.arrayBuffer())
        let binary = ''
        for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192))
        loaded.push({ asset_id: `asset_${index + 1}`, media_type: file.type, content_base64: btoa(binary) })
      }
      setAssets(loaded)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not read the assets.') }
    finally { setReading(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (submitting.current || reading) return
    submitting.current = true; setBusy(true); setError(''); setResult(null)
    try {
      setResult(await analyzeVisual({ brand_id: review?.brand_id ?? 'lumadesk', draft_id: review?.draft_id ?? standaloneId,
        draft_version: review?.draft_version ?? 'visual-input-v1', html, css, assets }))
    } catch (err) {
      setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'The visual service could not be reached. Check your connection and retry.')
    } finally { submitting.current = false; setBusy(false) }
  }
  return <div className="page-stack">
    <header className="page-heading"><p className="eyebrow">Brand presentation · static analysis</p><h1>Look closer at the details.</h1><p>Check logo bytes, configured palette targets, declared color contrast and HTML image descriptions.</p></header>
    <div className="demo-notice" role="note">These checks inspect passive HTML/CSS declarations and supplied PNG/JPEG assets. No HTML is rendered or executed. An active, approved server-side visual manifest is required. Results are temporary and do not change a review or record approval.</div>
    <div className="workspace-grid">
      <form className="review-panel visual-form" onSubmit={(event) => { void submit(event) }} aria-busy={busy}>
        <h2>Visual input</h2><p className="muted-copy">{review ? `Associated with draft ${review.draft_id} @ ${review.draft_version}. The returned input digest identifies this separate visual submission.` : 'Standalone visual input for fictional LumaDesk. Submit a text review separately for a human decision.'}</p>
        <label className="field-label" htmlFor="visual-html">Passive HTML<textarea id="visual-html" className="mono" rows={9} value={html} maxLength={100000} required disabled={busy} onChange={(event) => { setHtml(event.target.value); setResult(null) }} placeholder={'<div><p>Your copy</p><img src="asset:asset_1" alt="Describe the image"></div>'} /></label>
        <label className="field-label" htmlFor="visual-css">CSS declarations<textarea id="visual-css" className="mono" rows={5} value={css} maxLength={32000} disabled={busy} onChange={(event) => { setCss(event.target.value); setResult(null) }} placeholder="p { color: #1c1c18; background-color: #fcf9f2; }" /></label>
        <label className="field-label" htmlFor="visual-assets">PNG/JPEG assets (optional)<input id="visual-assets" type="file" multiple accept="image/png,image/jpeg" disabled={busy || reading} onChange={(event) => { void readAssets(event.target.files) }} /></label>
        {reading && <p role="status">Reading assets…</p>}
        {assets.length > 0 && <p className="muted-copy">In file order: {assets.map((asset) => `asset:${asset.asset_id}`).join(', ')}. Reference these IDs in HTML image src attributes.</p>}
        <p className="muted-copy">Up to 100,000 HTML characters, 32,000 CSS characters, 8 assets and 768 KiB total request. Scripts, event handlers, external image URLs, embedded documents and active content are rejected. Unsupported styles may return uncertainty.</p>
        <button className="accent-button" disabled={busy || reading || !html.trim()}><Icon name="search" />{busy ? 'Checking declarations…' : 'Run static visual checks'}</button>
      </form>
      <section className="visual-result" aria-label="Visual check results" aria-busy={busy}>
        <h2>Inspection results</h2>
        {error && <div className="error-box" role="alert"><p className="error-message">{error}</p><p className="muted-copy">A missing manifest requires administrator configuration. Your input is preserved for retry.</p></div>}
        {!result && <div className="empty-state" role={busy ? 'status' : undefined}><Icon name="image" /><h3>{busy ? 'Inspecting declarations…' : 'A clear view of the limits.'}</h3><p>Results appear here after a successful backend check. This is not a rendered-page or full WCAG assessment.</p></div>}
        {result && <><section className="review-panel"><p className="eyebrow">Static declarations · manifest {result.manifest_version}</p><h3>{result.findings.length} results returned</h3><dl className="provenance-rows"><dt>Draft</dt><dd><code>{result.draft_id} @ {result.draft_version}</code></dd><dt>Input SHA-256</dt><dd><code>{result.input_sha256}</code></dd><dt>Manifest SHA-256</dt><dd><code>{result.manifest_sha256}</code></dd><dt>Source</dt><dd>{result.source_id} @ {result.source_version}</dd><dt>Excerpt</dt><dd>{result.source_excerpt}</dd></dl></section>
          {!result.findings.length && <div className="empty-state"><h3>No applicable results</h3><p>No findings were returned for this input. This is not a compliance approval.</p></div>}
          {result.findings.map((finding, index) => <article className="finding-card" key={index}><div className="finding-header"><h3>{finding.check.replaceAll('_', ' ')}</h3><EvidenceStatusBadge status={finding.evidence_status} /></div><code>{finding.element} · {finding.result}</code><p>{finding.explanation}</p><details><summary>Measured evidence</summary><pre>{JSON.stringify(finding.evidence, null, 2)}</pre></details></article>)}
          <section className="review-panel"><h3>Scope & limitations</h3><ul className="intake-warnings">{result.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul></section>
        </>}
      </section>
    </div>
  </div>
}
