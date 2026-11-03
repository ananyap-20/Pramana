import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getActiveReviewHistory,
  getRetainedOriginal,
  auditRequest,
  loadCurrentReview,
  submitReviewDecision,
  ApiError,
  type AnalyzeResponse,
  type ReviewDecision,
  type ReviewDecisionEvent,
  type AuditIdentity,
} from '../api/client'
import { FindingCard } from '../components/FindingCard'
import { DocumentProvenance } from '../components/DocumentProvenance'

const DECISIONS: { value: ReviewDecision; label: string; description: string }[] = [
  { value: 'approved', label: 'Approve', description: 'Human reviewer accepts this draft.' },
  { value: 'revision', label: 'Request revision', description: 'Return the draft for changes.' },
  { value: 'rejected', label: 'Reject', description: 'Do not use this draft.' },
]

export function HumanReviewPage() {
  const [review] = useState<AnalyzeResponse | null>(() => loadCurrentReview())
  const [decisionHistory, setDecisionHistory] = useState<ReviewDecisionEvent[]>([])
  const [attested, setAttested] = useState(false)
  const [saving, setSaving] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [originalError, setOriginalError] = useState('')
  const [error, setError] = useState('')
  const [revision, setRevision] = useState<number | undefined>()
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const requestRef = useRef({ fingerprint: '', key: '' })
  const durable = review?.persistence === 'mongodb_encrypted_audit'
  const [canDecide, setCanDecide] = useState(!durable)

  const refreshHistory = useCallback(async () => {
    if (!review) return
    const records = await getActiveReviewHistory(review)
    const record = records.find((item) => item.review_run_id === review.review_run_id)
    setDecisionHistory(record?.decision_history ?? [])
    setRevision(record?.revision)
    setHistoryLoaded(true)
  }, [review])

  useEffect(() => {
    if (!review) return
    let cancelled = false
    getActiveReviewHistory(review)
      .then(async (records) => {
        const identity = durable ? await auditRequest<AuditIdentity>('/me') : null
        if (!cancelled) {
          const record = records.find((item) => item.review_run_id === review.review_run_id)
          setDecisionHistory(record?.decision_history ?? [])
          setRevision(record?.revision)
          setHistoryLoaded(true)
          setCanDecide(!identity || identity.role !== 'reader')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : 'Could not load review history.')
      })
    return () => { cancelled = true }
  }, [review, durable])

  async function handleDecision(decision: ReviewDecision) {
    if (!review || !attested || saving || !historyLoaded || !canDecide) return
    setSaving(true)
    setError('')
    try {
      const fingerprint = JSON.stringify([decision, revision])
      if (requestRef.current.fingerprint !== fingerprint) requestRef.current = { fingerprint, key: crypto.randomUUID() }
      const saved = await submitReviewDecision(review.review_run_id, decision, review, revision, requestRef.current.key)
      setDecisionHistory((current) => current.some((item) => item.decision_id === saved.decision_id) ? current : [...current, saved])
      setRevision(saved.revision)
      setAttested(false)
      if (durable) {
        setHistoryLoaded(false)
        try { await refreshHistory() } catch { setError('Decision saved. Reload decision history to see the latest revision.') }
      }
    } catch (err) {
      setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not save the decision.')
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) setCanDecide(false)
      if (err instanceof ApiError && err.status === 409) {
        setAttested(false)
        try { await refreshHistory() } catch { setHistoryLoaded(false) }
      }
    } finally {
      setSaving(false)
    }
  }

  async function downloadOriginal() {
    if (!review || downloading) return
    setDownloading(true)
    setOriginalError('')
    try {
      const blob = await getRetainedOriginal(review.review_run_id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      const kind = review.document_provenance?.file_type ?? review.input_type
      const extension = ['docx', 'pdf', 'png', 'jpeg', 'jpg'].includes(kind) ? kind : 'bin'
      link.href = url
      link.download = `pramana-original.${extension}`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setOriginalError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not download the retained original. Check the connection and retry.')
    } finally { setDownloading(false) }
  }

  const latestDecision = decisionHistory.length
    ? decisionHistory[decisionHistory.length - 1]
    : null

  return (
    <div className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">LumaDesk · fictional demo brand</p>
        <h1>Human review</h1>
        <p>Inspect the submitted draft and its evidence before recording a decision.</p>
      </header>

      {!review ? (
        <section className="empty-state" aria-live="polite">
          <h2>No active review run</h2>
          <p>Analyze a draft first. This page will then show that exact draft and its validated findings.</p>
          <button className="primary-button" onClick={() => { window.location.hash = '#/draft-workspace' }}>
            Go to draft workspace
          </button>
        </section>
      ) : (
        <>
          <section className="review-summary" aria-label="Review run summary">
            <div><span className="summary-label">Review run</span><code>{review.review_run_id}</code></div>
            <div><span className="summary-label">Draft version</span><strong>{review.draft_version}</strong></div>
            <div><span className="summary-label">Validated findings</span><strong>{review.findings.length}</strong></div>
            <div><span className="summary-label">Current decision</span><strong>{latestDecision?.decision ?? 'Not recorded'}</strong></div>
          </section>

          <div className="human-review-layout"><div className="review-reading-column">
          <section className="reading-section">
            <h2>Submitted draft</h2>
            <p className="muted-copy">Exact text returned by the analysis run. {review.document_provenance ? 'Analyzed from the confirmed document transcription.' : review.input_type === 'docx' ? 'Extracted from an ordinary-paragraph DOCX.' : 'Submitted as plain text.'}</p>
            <pre className="draft-preview">{review.draft_text}</pre>
            {durable && review.input_type !== 'plain_text' && <>
              <button className="secondary-button" disabled={downloading} onClick={() => { void downloadOriginal() }}>{downloading ? 'Downloading…' : 'Download retained original'}</button>
              <p className="muted-copy">Requires configured private-file storage and an original retained for this run. Extraction previews may expire separately.</p>
              {originalError && <p className="error-message" role="alert">{originalError}</p>}
            </>}
          </section>

          <DocumentProvenance review={review} />

          <section className="reading-section">
            <h2>Evidence to review <span className="count-pill">{review.findings.length}</span></h2>
            {review.findings.length ? (
              <div className="review-findings">
                {review.findings.map((finding, index) => (
                  <FindingCard key={finding.finding_id} finding={finding} expanded collapsible initiallyOpen={index === 0} />
                ))}
              </div>
            ) : (
              <p className="empty-inline">No findings were returned by the four seeded deterministic checks. This is not a general guarantee that the draft is compliant.</p>
            )}
          </section>

          </div><aside className="decision-panel">
            <h2>Record a human decision</h2>
            <label className="attestation">
              <input type="checkbox" checked={attested} onChange={(event) => setAttested(event.target.checked)} />
              <span>I reviewed this draft and its findings. The final use decision remains mine.</span>
            </label>
            <div className="decision-actions">
              {DECISIONS.map((item) => (
                <button
                  className={item.value === 'approved' ? 'primary-button' : 'secondary-button'}
                  key={item.value}
                  type="button"
                  disabled={!attested || saving || !historyLoaded || !canDecide}
                  onClick={() => { void handleDecision(item.value) }}
                >
                  {saving ? 'Saving…' : item.label}
                </button>
              ))}
            </div>
            <p className="muted-copy">Each selection appends a timestamped decision to this run. New decisions do not erase prior ones.</p>
            {error && <p className="error-message" role="alert">{error}</p>}
            {durable && historyLoaded && !canDecide && <p className="muted-copy">Reviewer access is required to record a decision. Your current access allows viewing this review.</p>}
            {!historyLoaded && <button className="secondary-button" onClick={() => { void refreshHistory().catch(() => setError('Could not refresh review history.')) }}>Reload decision history</button>}
            {decisionHistory.length > 0 && (
              <ol className="decision-history" aria-label="Decision history">
                {decisionHistory.map((item) => (
                  <li key={item.decision_id}>
                    <strong>{item.decision}</strong>
                    {item.actor_id && <span>{item.actor_id} · revision {item.revision}</span>}
                    <time dateTime={item.decided_at}>{new Date(item.decided_at).toLocaleString()}</time>
                  </li>
                ))}
              </ol>
            )}
          </aside></div>
        </>
      )}
    </div>
  )
}
