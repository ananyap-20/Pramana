import { useEffect, useRef, useState } from 'react'
import {
  ApiError, createExtraction, getExtractionPreview, intakeRequest,
  type AnalyzeResponse, type ExtractionResponse,
} from '../api/client'

export function DocumentIntakePanel({ file, brandId, onAnalyzed, onInvalidated }: {
  file: File; brandId: string; onAnalyzed: (result: AnalyzeResponse) => void; onInvalidated: () => void
}) {
  const [job, setJob] = useState<ExtractionResponse | null>(null)
  const [texts, setTexts] = useState<string[]>([])
  const [attested, setAttested] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const controller = useRef<AbortController | null>(null)
  const activeId = useRef<string | null>(null)
  const processing = useRef(false)
  const urls = useRef<string[]>([])
  const mounted = useRef(true)
  const submitting = useRef(false)

  useEffect(() => {
    mounted.current = true
    const previewHandles = urls.current
    return () => {
      mounted.current = false
      controller.current?.abort()
      previewHandles.forEach(URL.revokeObjectURL)
      if (processing.current && activeId.current) void intakeRequest(activeId.current, '/cancel', {}).catch(() => {})
    }
  }, [])

  useEffect(() => {
    if (!job || job.state === 'expired') return
    const timer = window.setTimeout(() => {
      controller.current?.abort()
      setJob((current) => current ? { ...current, state: 'expired', current: null } : current)
      setTexts([])
      setPreviewUrls([])
      urls.current.forEach(URL.revokeObjectURL)
      onInvalidated()
    }, Math.max(0, Date.parse(job.expires_at) - Date.now()))
    return () => window.clearTimeout(timer)
  }, [job, onInvalidated])

  function report(err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') return
    if (mounted.current) setError(err instanceof ApiError ? err.detail : 'Connection interrupted. Retry or upload the file again.')
  }

  async function extract() {
    if (submitting.current) return
    submitting.current = true
    controller.current = new AbortController()
    const signal = controller.current.signal
    setBusy('Uploading file…')
    setError('')
    onInvalidated()
    try {
      let current = await createExtraction(brandId, file, signal)
      activeId.current = current.extraction_id
      processing.current = true
      if (!mounted.current) return
      setJob(current)
      while (current.state === 'queued' || current.state === 'processing') {
        setBusy(current.state === 'queued' ? 'Queued for extraction…' : 'Extracting text and checking pages…')
        await new Promise((resolve) => window.setTimeout(resolve, 500))
        current = await intakeRequest<ExtractionResponse>(current.extraction_id, '', undefined, signal)
        if (!mounted.current) return
        setJob(current)
      }
      processing.current = false
      if (current.state === 'failed') throw new ApiError(422, current.error ?? 'Extraction failed.')
      if (!current.current) throw new ApiError(410, 'The extraction expired. Upload the original again.')
      setTexts(current.current.pages.map((page) => page.text))
      const previews = []
      for (const page of current.current.pages) {
        const blob = await getExtractionPreview(current.extraction_id, page.page, signal)
        if (!mounted.current) return
        const url = URL.createObjectURL(blob)
        urls.current.push(url)
        previews.push(url)
      }
      setPreviewUrls(previews)
    } catch (err) {
      report(err)
    } finally {
      submitting.current = false
      if (mounted.current) setBusy('')
    }
  }

  async function confirm() {
    if (!job?.current || !attested || submitting.current) return
    submitting.current = true
    setBusy('Saving confirmed transcription…')
    setError('')
    onInvalidated()
    try {
      const current = await intakeRequest<ExtractionResponse>(job.extraction_id, '/confirm', {
        version: job.current.version, text_sha256: job.current.text_sha256,
        page_texts: texts, confirm_transcription: true,
      })
      if (mounted.current) { setJob(current); setAttested(false) }
    } catch (err) { report(err) } finally { submitting.current = false; if (mounted.current) setBusy('') }
  }

  async function analyze() {
    if (!job?.current || job.state !== 'ready' || submitting.current) return
    submitting.current = true
    setBusy('Analysing confirmed text…')
    setError('')
    try {
      const result = await intakeRequest<AnalyzeResponse>(job.extraction_id, '/analyze', {
        version: job.current.version, text_sha256: job.current.text_sha256,
      })
      if (mounted.current) onAnalyzed(result)
    } catch (err) { report(err) } finally { submitting.current = false; if (mounted.current) setBusy('') }
  }

  async function cancel() {
    controller.current?.abort()
    if (activeId.current) {
      try { await intakeRequest(activeId.current, '/cancel', {}) } catch (err) { report(err) }
    }
    processing.current = false
    setJob((current) => current ? { ...current, state: 'expired', current: null } : current)
    setTexts([])
    setPreviewUrls([])
    urls.current.forEach(URL.revokeObjectURL)
    onInvalidated()
  }

  const changed = job?.current?.pages.some((page, index) => page.text !== texts[index]) ?? false
  const characterCount = Array.from(texts.join('\n\n')).length
  const canConfirm = !!job?.current && !busy && attested && characterCount > 0 && characterCount <= 100_000
    && (job.state === 'needs_confirmation' || changed)
  const canAnalyze = job?.state === 'ready' && !changed && !busy

  return (
    <div className="intake-panel">
      <h3>PDF / image transcription</h3>
      <p className="muted-copy">English printed text, upright pages. Up to 5 MiB, 10 PDF pages, 12 million pixels per page/image and 100,000 characters. Columns and tables need careful comparison; handwriting is outside this demo’s supported scope.</p>
      <p className="muted-copy">Extraction previews and working versions expire after 15 minutes or a server restart. Completed organization reviews follow audit retention; original-file retention depends on server configuration. Use fictional files for this prototype.</p>
      {(!job || job.state === 'failed' || job.state === 'expired') && (
        <button type="button" className="primary-button" disabled={!!busy} onClick={() => { void extract() }}>Extract text</button>
      )}
      <p role="status" aria-live="polite">{busy || (job ? `Extraction: ${job.state.replaceAll('_', ' ')}` : 'Select Extract text to start.')}</p>
      {job && job.state !== 'expired' && <button type="button" className="secondary-button" onClick={() => { void cancel() }}>Discard extraction</button>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {job?.state === 'expired' && <p role="alert">This extraction expired or was discarded. Extract the original again before analysis.</p>}
      {job?.current && (
        <>
          <p className="muted-copy">Version {job.current.version} · {characterCount.toLocaleString()} characters · Expires {new Date(job.expires_at).toLocaleTimeString()}</p>
          <ul className="intake-warnings">{job.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          {job.current.pages.map((page, index) => (
            <section className="intake-page" key={page.page} aria-label={`Page ${page.page} transcription`}>
              <h4>Page {page.page} · {page.method === 'pdf_text' ? 'PDF text layer' : page.method === 'ocr' ? 'OCR — check transcription' : 'Human-edited transcription'}</h4>
              {previewUrls[index] ? <a href={previewUrls[index]} target="_blank" rel="noreferrer" aria-label={`Open page ${page.page} preview`}><img src={previewUrls[index]} alt={`Rendered original page ${page.page}; compare with the transcription below`} /></a> : <p className="muted-copy">Loading page preview…</p>}
              <ul className="intake-warnings">{page.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
              <label htmlFor={`page-text-${page.page}`}>Check and correct page {page.page} text</label>
              <textarea id={`page-text-${page.page}`} value={texts[index] ?? ''} rows={7} disabled={!!busy}
                onChange={(event) => {
                  setTexts((current) => current.map((text, i) => i === index ? event.target.value : text))
                  setAttested(false)
                  onInvalidated()
                }} />
              <p className="muted-copy">{page.regions.length} source regions · {page.coordinates.replaceAll('_', ' ')}. Edited text will have no original-file coordinates.</p>
            </section>
          ))}
          {characterCount > 100_000 && <p className="error-message" role="alert">The corrected text exceeds 100,000 characters. Nothing will be truncated.</p>}
          <label className="attestation">
            <input type="checkbox" checked={attested} disabled={!!busy} onChange={(event) => setAttested(event.target.checked)} />
            <span>I compared every page with its preview and checked missing text and reading order. This confirms transcription only; content approval comes later.</span>
          </label>
          <div className="decision-actions">
            <button type="button" className="secondary-button" disabled={!canConfirm} onClick={() => { void confirm() }}>Confirm transcription</button>
            <button type="button" className="primary-button" disabled={!canAnalyze} onClick={() => { void analyze() }}>Analyse confirmed text</button>
          </div>
          <details className="intake-provenance"><summary>Extraction provenance</summary>
            <p>Original SHA-256: <code>{job.file_sha256}</code></p>
            <p>Text SHA-256: <code>{job.current.text_sha256}</code></p>
            <p>{Object.entries(job.tools).map(([name, version]) => `${name}: ${version}`).join(' · ')}</p>
            <p>{job.extraction_seconds === null ? '' : `Extraction took ${job.extraction_seconds.toFixed(2)} seconds on this server.`}</p>
          </details>
        </>
      )}
    </div>
  )
}
