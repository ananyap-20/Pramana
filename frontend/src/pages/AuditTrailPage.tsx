import { useEffect, useState } from 'react'
import { ApiError, getAuditToken, getReviewHistory, type ReviewRunSummary } from '../api/client'
import { ReviewLedger } from '../components/ReviewLedger'
import { AuditDashboard } from './AuditDashboard'

export function AuditTrailPage() {
  return getAuditToken() ? <AuditDashboard /> : <DemoHistory />
}
function DemoHistory() {
  const [records, setRecords] = useState<ReviewRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getReviewHistory('lumadesk', controller.signal).then((value) => { if (!controller.signal.aborted) setRecords(value) })
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not load the review history.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [attempt])
  return <div className="page-stack">
    <header className="page-heading page-heading-row"><div><p className="eyebrow">The review ledger · shared demo</p><h1>A record of every decision.</h1><p>Review runs and explicit human decisions returned by the demo API.</p></div><button className="secondary-button" disabled={loading} onClick={() => { setLoading(true); setError(''); setRecords([]); setAttempt((n) => n + 1) }}>{loading ? 'Refreshing…' : 'Refresh history'}</button></header>
    <div className="demo-notice">Shared demo history is unauthenticated, retains metadata only and returns up to 100 recent runs. Its persistence depends on backend configuration. Temporary PDF/image reviews are separate. <a href="#/reviewer-access">Connect organization access</a> for protected snapshots and analytics.</div>
    {error && <p className="error-message error-box" role="alert">{error}</p>}
    {loading && <p role="status">Loading review history…</p>}
    {!loading && !error && <><section className="review-summary metrics-summary" aria-label="Loaded demo record counts"><div><span className="summary-label">Returned review runs</span><strong>{records.length}</strong></div><div><span className="summary-label">Validated findings</span><strong>{records.reduce((sum, r) => sum + r.finding_count, 0)}</strong></div><div><span className="summary-label">Human decision events</span><strong>{records.reduce((sum, r) => sum + r.decision_history.length, 0)}</strong></div><div><span className="summary-label">Awaiting a decision</span><strong>{records.filter((r) => !r.current_decision).length}</strong></div></section><ReviewLedger records={records} durable={false} /></>}
  </div>
}
