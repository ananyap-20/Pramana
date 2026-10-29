import { useEffect, useState } from 'react'
import {
  getReviewHistory,
  loadCurrentReview,
  submitReviewDecision,
  ApiError,
  type AnalyzeResponse,
  type ReviewDecision,
  type ReviewDecisionEvent,
} from '../api/client'
import { FindingCard } from '../components/FindingCard'

const DEMO_BRAND_ID = 'lumadesk'

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
  const [error, setError] = useState('')

  useEffect(() => {
    if (!review) return
    let cancelled = false
    getReviewHistory(DEMO_BRAND_ID)
      .then((records) => {
        if (!cancelled) {
          const record = records.find((item) => item.review_run_id === review.review_run_id)
          setDecisionHistory(record?.decision_history ?? [])
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : 'Could not load review history.')
      })
    return () => { cancelled = true }
  }, [review])

  async function handleDecision(decision: ReviewDecision) {
    if (!review || !attested || saving) return
    setSaving(true)
    setError('')
    try {
      const saved = await submitReviewDecision(review.review_run_id, decision)
      setDecisionHistory((current) => [...current, saved])
    } catch (err) {
      setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not save the decision.')
    } finally {
      setSaving(false)
    }
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
          <div className="demo-notice" role="note">
            Demo decisions are unauthenticated and held in shared process memory. They are review records for this demonstration, not verified identities or legal approvals.
          </div>

          <section className="review-summary" aria-label="Review run summary">
            <div><span className="summary-label">Review run</span><code>{review.review_run_id}</code></div>
            <div><span className="summary-label">Draft version</span><strong>{review.draft_version}</strong></div>
            <div><span className="summary-label">Validated findings</span><strong>{review.findings.length}</strong></div>
            <div><span className="summary-label">Current decision</span><strong>{latestDecision?.decision ?? 'Not recorded'}</strong></div>
          </section>

          <section className="review-panel">
            <h2>Submitted draft</h2>
            <p className="muted-copy">Exact text returned by the analysis run. {review.input_type === 'docx' ? 'Extracted from an ordinary-paragraph DOCX.' : 'Submitted as plain text.'}</p>
            <pre className="draft-preview">{review.draft_text}</pre>
          </section>

          <section className="review-panel">
            <h2>Evidence to review <span className="count-pill">{review.findings.length}</span></h2>
            {review.findings.length ? (
              <div className="review-findings">
                {review.findings.map((finding) => (
                  <FindingCard key={finding.finding_id} finding={finding} expanded />
                ))}
              </div>
            ) : (
              <p className="empty-inline">No findings were returned by the four seeded deterministic checks. This is not a general guarantee that the draft is compliant.</p>
            )}
          </section>

          <section className="review-panel">
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
                  disabled={!attested || saving}
                  onClick={() => { void handleDecision(item.value) }}
                >
                  {saving ? 'Saving…' : item.label}
                </button>
              ))}
            </div>
            <p className="muted-copy">Each selection appends a timestamped decision to this run. New decisions do not erase prior ones.</p>
            {error && <p className="error-message" role="alert">{error}</p>}
            {decisionHistory.length > 0 && (
              <ol className="decision-history" aria-label="Decision history">
                {decisionHistory.map((item) => (
                  <li key={item.decision_id}>
                    <strong>{item.decision}</strong>
                    <time dateTime={item.decided_at}>{new Date(item.decided_at).toLocaleString()}</time>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </div>
  )
}
