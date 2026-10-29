import { useCallback, useEffect, useState } from 'react'
import { ApiError, getReviewHistory, type ReviewRunSummary } from '../api/client'

const DEMO_BRAND_ID = 'lumadesk'

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function AuditTrailPage() {
  const [records, setRecords] = useState<ReviewRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setRecords(await getReviewHistory(DEMO_BRAND_ID))
    } catch (err) {
      setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not load the review history.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  return (
    <div className="page-stack">
      <header className="page-heading page-heading-row">
        <div>
          <p className="eyebrow">LumaDesk · fictional demo brand</p>
          <h1>Review history</h1>
          <p>Recent analysis runs and human decisions recorded by the demo API.</p>
        </div>
        <button className="secondary-button" onClick={() => { void refresh() }} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh history'}
        </button>
      </header>

      <div className="demo-notice" role="note">
        Shared demo history is unauthenticated, limited to the latest 100 runs, and stored only in process memory. It does not retain draft text or receipt passages; all records disappear when the service restarts.
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}
      {loading && <p className="loading-copy" aria-live="polite">Loading review history…</p>}
      {!loading && !error && records.length === 0 && (
        <section className="empty-state">
          <h2>No review runs yet</h2>
          <p>Analyze a LumaDesk draft to create the first history record.</p>
          <button className="primary-button" onClick={() => { window.location.hash = '#/draft-workspace' }}>
            Analyze a draft
          </button>
        </section>
      )}

      {!loading && records.length > 0 && (
        <div className="history-list">
          {records.map((record) => (
            <article className="history-card" key={record.review_run_id}>
              <div className="history-card-top">
                <div>
                  <span className="summary-label">Review run</span>
                  <code>{record.review_run_id}</code>
                </div>
                <time dateTime={record.evaluated_at}>{formatDate(record.evaluated_at)}</time>
              </div>
              <div className="history-stats">
                <span><strong>{record.finding_count}</strong> validated findings</span>
                <span>Draft {record.draft_id.slice(0, 8)}… · {record.draft_version}</span>
                <span>
                  Latest decision: <strong>{record.current_decision ?? 'Not recorded'}</strong>
                  {record.current_decision_at ? ` · ${formatDate(record.current_decision_at)}` : ''}
                </span>
              </div>
              {record.decision_history.length > 1 && (
                <details className="history-decisions">
                  <summary>{record.decision_history.length} decisions recorded</summary>
                  <ol className="decision-history">
                    {record.decision_history.map((decision) => (
                      <li key={decision.decision_id}>
                        <strong>{decision.decision}</strong>
                        <time dateTime={decision.decided_at}>{formatDate(decision.decided_at)}</time>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
