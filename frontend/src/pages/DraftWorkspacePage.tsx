import { useCallback, useRef, useState } from 'react'
import {
  analyzeDocument, analyzeDraft, ApiError, clearCurrentReview,
  loadCurrentReview, saveCurrentReview, type AnalyzeResponse,
} from '../api/client'
import { FindingCard } from '../components/FindingCard'
import { DocumentIntakePanel } from '../components/DocumentIntakePanel'
import { Icon } from '../components/Icon'

const DEMO_DRAFT = 'Our new LumaDesk dashboard is guaranteed to eliminate all errors for your entire team. The starter plan supports 50 team members. Features and pricing vary by plan. Get started this quarter with our enterprise tier.'
type SubmitState = 'idle' | 'loading' | 'done' | 'error'

export function DraftWorkspacePage() {
  const [initialReview] = useState(loadCurrentReview)
  const [draftText, setDraftText] = useState(initialReview?.draft_text ?? DEMO_DRAFT)
  const [result, setResult] = useState<AnalyzeResponse | null>(initialReview)
  const [submitState, setSubmitState] = useState<SubmitState>(initialReview ? 'done' : 'idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const submittingRef = useRef(false)
  const requestRef = useRef({ fingerprint: '', key: '' })
  const isPdfImage = !!file && !file.name.toLowerCase().endsWith('.docx')
  const invalidate = useCallback(() => { setResult(null); clearCurrentReview(); setSubmitState('idle'); setErrorMsg('') }, [])

  function acceptDocumentAnalysis(response: AnalyzeResponse) {
    saveCurrentReview(response)
    setResult(response)
    setDraftText(response.draft_text)
    setSubmitState('done')
  }

  async function handleAnalyze() {
    if (submittingRef.current || isPdfImage) return
    submittingRef.current = true
    clearCurrentReview()
    setSubmitState('loading')
    setErrorMsg('')
    setResult(null)
    try {
      if (!file && !draftText.trim()) throw new Error('Enter draft text before analyzing.')
      const fingerprint = file ? JSON.stringify(['lumadesk', file.name, file.size, file.lastModified]) : JSON.stringify(['lumadesk', draftText])
      if (requestRef.current.fingerprint !== fingerprint) requestRef.current = { fingerprint, key: crypto.randomUUID() }
      const response = file ? await analyzeDocument('lumadesk', file, requestRef.current.key)
        : await analyzeDraft({ brand_id: 'lumadesk', draft_text: draftText }, requestRef.current.key)
      acceptDocumentAnalysis(response)
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : err instanceof Error ? err.message : 'Analysis failed. Check the connection and retry.')
      setSubmitState('error')
    } finally { submittingRef.current = false }
  }

  function selectFile(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    invalidate()
    setFile(null)
    if (selected && (!/\.(docx|pdf|png|jpe?g)$/i.test(selected.name) || selected.size > 5 * 1024 * 1024)) {
      setErrorMsg('Choose a DOCX, PDF, PNG or JPEG file, no larger than 5 MiB.')
      setSubmitState('error')
      event.target.value = ''
      return
    }
    setFile(selected)
  }

  const busy = submitState === 'loading'
  const wordCount = draftText.trim() ? draftText.trim().split(/\s+/).length : 0

  return <div className="page-stack">
    <header className="page-heading page-heading-row">
      <div><p className="eyebrow">The editorial workspace · LumaDesk</p><h1>Review your draft.</h1>
        <p>Check your draft against active brand rules. Trace every finding to its evidence, then make the final call.</p></div>
      <a className="secondary-button" href="#/brand-guidelines-and-rules"><Icon name="shield" />Explore active policies</a>
    </header>
    <p className="workspace-note">Fictional LumaDesk sample · <a href="#/guide">Review and retention guide</a></p>
    <div className="workspace-grid">
      <section className="editor-panel" aria-label="Draft editor">
        <div className="editor-toolbar"><h2>Manuscript</h2><span className="category-badge">LumaDesk · fictional brand</span></div>
        <div className="editor-body">
          {file && isPdfImage ? <DocumentIntakePanel key={`${file.name}-${file.lastModified}-${file.size}`} file={file} brandId="lumadesk" onAnalyzed={acceptDocumentAnalysis} onInvalidated={invalidate} />
            : file ? <div className="empty-state"><Icon name="file" /><h3>{file.name}</h3><p>{(file.size / 1024).toFixed(1)} KiB · ordinary-paragraph DOCX extraction. Select Analyze draft to extract and evaluate.</p></div>
            : <><label className="eyebrow" htmlFor="draft-text">Your working draft</label><textarea id="draft-text" className="draft-editor" value={draftText} disabled={busy} maxLength={100_000} rows={14}
              onChange={(event) => { setDraftText(event.target.value); invalidate() }} placeholder="Paste or write your draft here…" aria-describedby="editor-limit" /></>}
        </div>
        <div className="editor-footer"><span id="editor-limit">{file ? file.name : `${wordCount} words · ${Array.from(draftText).length.toLocaleString()} characters`}</span>
          {!file && <button className="text-button" disabled={busy} onClick={() => { setDraftText(''); invalidate() }}>Clear draft</button>}</div>
        <div className="editor-toolbar" data-tour="draft-actions">
          <div className="decision-actions"><button className="secondary-button" data-tour="import" onClick={() => fileInputRef.current?.click()} disabled={busy}><Icon name="upload" />Import file</button>
            {file && <button className="text-button" disabled={busy} onClick={() => { setFile(null); invalidate(); if (fileInputRef.current) fileInputRef.current.value = '' }}>Remove file</button>}</div>
          {!isPdfImage && <button className="accent-button" onClick={() => { void handleAnalyze() }} disabled={busy || (!file && !draftText.trim())}>{busy ? 'Analyzing…' : 'Analyze draft'}<Icon name="arrow" /></button>}
          <input ref={fileInputRef} type="file" aria-label="Upload document or image" accept=".docx,.pdf,.png,.jpg,.jpeg" hidden onChange={selectFile} />
        </div>
        <p className="ledger-caption">DOCX, PDF, PNG or JPEG · up to 5 MiB. PDF/image intake requires backend configuration and transcription confirmation.</p>
      </section>
      <section className="findings-column" aria-label="Analysis findings" aria-busy={busy}>
        <div className="section-topline"><h2>Review desk</h2><span className="panel-label">{result ? `${result.findings.length} validated findings` : 'Awaiting analysis'}</span></div>
        {errorMsg && <div className="error-box" role="alert"><p className="error-message">{errorMsg}</p><p className="muted-copy">Your input is still available. Resolve the error and retry.</p></div>}
        {busy && <div className="empty-state" role="status"><Icon name="search" /><h3>Checking your manuscript</h3><p>Evaluating the submitted version against the configured rules and validating its evidence.</p></div>}
        {!busy && !result && <div className="empty-state"><Icon name="shield" /><h3>A second pair of eyes.</h3><p>Run a review to see findings here. Every returned receipt identifies the rule, source version and exact draft passage where applicable.</p><a href="#/guide">How review works</a></div>}
        {result && <><div className="review-panel"><p className="eyebrow">Analysis complete · human review required</p><h3>{result.findings.length ? 'A few things to look at.' : 'No findings from the seeded checks.'}</h3>
          <p className="muted-copy">This result covers the configured rules. It does not establish general compliance or approve publication.</p><code>Run {result.review_run_id} · {result.draft_version}</code></div>
          <div className="review-findings">{result.findings.map((finding, index) => <FindingCard key={finding.finding_id} finding={finding} collapsible initiallyOpen={index === 0} />)}</div>
          <div className="decision-actions"><a className="primary-button" href="#/review-and-sign-off">Continue to human review<Icon name="arrow" /></a><a className="secondary-button" href="#/evidence-receipts">Inspect evidence</a></div></>}
      </section>
    </div>
  </div>
}
