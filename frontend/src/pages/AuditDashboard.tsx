import { useEffect, useState } from 'react'
import { ApiError, auditRequest, saveCurrentReview, type AnalyzeResponse, type AuditAnalytics, type AuditHistory, type ReviewRunSummary } from '../api/client'

const BRAND = 'lumadesk'

function message(error: unknown): string {
  return error instanceof ApiError ? error.detail : 'Could not load saved reviews. Check the connection and retry.'
}

function utc(value: string): string {
  return new Date(value).toLocaleString(undefined, { timeZone: 'UTC', timeZoneName: 'short' })
}

export function AuditDashboard() {
  const [days, setDays] = useState(30)
  const [refresh, setRefresh] = useState(0)
  const [metrics, setMetrics] = useState<AuditAnalytics | null>(null)
  const [records, setRecords] = useState<ReviewRunSummary[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [moreLoading, setMoreLoading] = useState(false)
  const [opening, setOpening] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      auditRequest<AuditAnalytics>(`/analytics/${BRAND}?days=${days}`, { signal: controller.signal }),
      auditRequest<AuditHistory>(`/reviews/history/${BRAND}`, { signal: controller.signal }),
    ]).then(([analytics, history]) => {
      if (controller.signal.aborted) return
      setMetrics(analytics)
      setRecords(history.records)
      setCursor(history.next_cursor)
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) setError(message(err))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [days, refresh])

  async function more() {
    if (!cursor || moreLoading) return
    setMoreLoading(true)
    setError('')
    try {
      const result = await auditRequest<AuditHistory>(`/reviews/history/${BRAND}?cursor=${encodeURIComponent(cursor)}`)
      setRecords((previous) => [...previous, ...result.records.filter((record) => !previous.some((item) => item.review_run_id === record.review_run_id))])
      setCursor(result.next_cursor)
    } catch (err) { setError(message(err)) } finally { setMoreLoading(false) }
  }

  async function open(record: ReviewRunSummary) {
    setOpening(record.review_run_id)
    setError('')
    try {
      const snapshot = await auditRequest<{ analysis: AnalyzeResponse }>(`/reviews/${encodeURIComponent(record.review_run_id)}/snapshot`)
      saveCurrentReview(snapshot.analysis)
      window.location.assign('#/review-and-sign-off')
    } catch (err) { setError(message(err)) } finally { setOpening('') }
  }

  return <div className="page-stack">
    <header className="page-heading page-heading-row">
      <div><h1>Audit and analytics</h1><p>Saved reviews and human decisions for your organization.</p></div>
      <div className="decision-actions">
        <label>Analytics period <select value={days} onChange={(event) => { setDays(Number(event.target.value)); setLoading(true); setMetrics(null); setRecords([]); setCursor(null); setError('') }} disabled={loading || moreLoading}>
          {[7, 30, 90].map((value) => <option key={value} value={value}>Last {value} days</option>)}
        </select></label>
        <button className="secondary-button" disabled={loading || moreLoading} onClick={() => { setLoading(true); setMetrics(null); setRecords([]); setCursor(null); setError(''); setRefresh((value) => value + 1) }}>Refresh</button>
      </div>
    </header>
    {error && <p className="error-message" role="alert">{error}</p>}
    {loading && <p role="status">Loading saved reviews and totals…</p>}
    {metrics && <>
      <p className="muted-copy">{utc(metrics.period_start)} – {utc(metrics.period_end)} · updated {utc(metrics.generated_at)}</p>
      <section className="review-summary" aria-label="Review totals">
        <div><span className="summary-label">Completed analyses</span><strong>{metrics.total_runs}</strong></div>
        <div><span className="summary-label">Validated findings</span><strong>{metrics.total_findings}</strong></div>
        <div><span className="summary-label">Human decision events</span><strong>{metrics.decision_events}</strong></div>
        <div><span className="summary-label">Awaiting a decision</span><strong>{metrics.outcomes.pending ?? 0}</strong></div>
      </section>
      <section className="review-panel">
        <h2>Latest review outcomes</h2>
        <div className="history-stats">{Object.entries(metrics.outcomes).map(([outcome, count]) => <span key={outcome}>{outcome}: <strong>{count}</strong></span>)}</div>
        <p className="muted-copy">Every retained completed analysis in this period counts once. Corrections change the latest outcome and preserve previous decision events.</p>
      </section>
      <section className="review-panel"><h2>Findings by category</h2>
        {Object.keys(metrics.categories).length ? <div className="history-stats">{Object.entries(metrics.categories).map(([category, count]) => <span key={category}>{category.replaceAll('_', ' ')}: <strong>{count}</strong></span>)}</div> : <p>No validated findings in this period.</p>}
      </section>
      <section className="review-panel"><h2>Most frequent rule findings · up to 100 rules</h2>
        {metrics.repeated_rules.length ? <table className="audit-table"><thead><tr><th>Rule</th><th>Version</th><th>Findings</th></tr></thead><tbody>{metrics.repeated_rules.map((rule) => <tr key={`${rule.rule_id}:${rule.version}`}><td>{rule.rule_id}</td><td>{rule.version}</td><td>{rule.count}</td></tr>)}</tbody></table> : <p>No rule findings in this period.</p>}
      </section>
      <section className="review-panel"><h2>Daily analysis totals · UTC</h2>
        {metrics.daily.length ? <table className="audit-table"><thead><tr><th>Date</th><th>Analyses</th><th>Findings</th></tr></thead><tbody>{metrics.daily.map((day) => <tr key={day.date}><td>{day.date}</td><td>{day.runs}</td><td>{day.findings}</td></tr>)}</tbody></table> : <p>No completed analyses in this period.</p>}
      </section>
      <p className="muted-copy">{metrics.definition}</p>
    </>}
    {!loading && metrics && <section className="history-list" aria-label="Retained review history">
      <h2>Recent retained reviews · all dates</h2>
      {!records.length && <p>No saved reviews yet. Analyze a draft while organization audit access is connected.</p>}
      {records.map((record) => <article className="history-card" key={record.review_run_id}>
        <div className="history-card-top"><code>{record.review_run_id}</code><time dateTime={record.evaluated_at}>{new Date(record.evaluated_at).toLocaleString()}</time></div>
        <div className="history-stats"><span>{record.finding_count} validated findings</span><span>Latest: {record.current_decision ?? 'pending'}</span><span>Revision {record.revision}</span><span>Created by {record.actor_id}</span></div>
        <p className="muted-copy">Retained until {record.expires_at ? new Date(record.expires_at).toLocaleString() : 'not specified'}. Original upload previews may expire earlier; the saved evaluated text and evidence remain available.</p>
        <details><summary>{record.decision_history.length} decision events</summary><ol className="decision-history">{record.decision_history.map((event) => <li key={event.decision_id}><strong>{event.decision}</strong><span>{event.actor_id} · revision {event.revision}</span><time dateTime={event.decided_at}>{new Date(event.decided_at).toLocaleString()}</time></li>)}</ol></details>
        <button className="secondary-button" disabled={!!opening} onClick={() => { void open(record) }}>{opening === record.review_run_id ? 'Opening…' : 'Open saved review'}</button>
      </article>)}
      {cursor && <button className="secondary-button" disabled={moreLoading} onClick={() => { void more() }}>{moreLoading ? 'Loading…' : 'Load older reviews'}</button>}
    </section>}
  </div>
}
