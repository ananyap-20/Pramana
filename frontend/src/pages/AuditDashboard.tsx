import { useEffect, useState } from 'react'
import { ApiError, auditRequest, getReviewHistory, hasRetainedAudit, type AuditAnalytics, type AuditHistory, type ReviewRunSummary } from '../api/client'
import { ReviewLedger } from '../components/ReviewLedger'

function utc(value: string) { return new Date(value).toLocaleString(undefined, { timeZone: 'UTC', timeZoneName: 'short' }) }
function message(error: unknown) { return error instanceof ApiError ? `API error ${error.status}: ${error.detail}` : 'Could not load saved reviews. Check the connection and retry.' }

export function AuditDashboard() {
  const [days, setDays] = useState(30)
  const [refresh, setRefresh] = useState(0)
  const [metrics, setMetrics] = useState<AuditAnalytics | null>(null)
  const [records, setRecords] = useState<ReviewRunSummary[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [moreLoading, setMoreLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    if (!hasRetainedAudit()) {
      getReviewHistory('lumadesk', controller.signal)
        .then((history) => { if (!controller.signal.aborted) setRecords(history) })
        .catch((err: unknown) => { if (!controller.signal.aborted) setError(message(err)) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
      return () => controller.abort()
    }
    Promise.all([auditRequest<AuditAnalytics>(`/analytics/lumadesk?days=${days}`, { signal: controller.signal }),
      auditRequest<AuditHistory>('/reviews/history/lumadesk', { signal: controller.signal })])
      .then(([analytics, history]) => { if (!controller.signal.aborted) { setMetrics(analytics); setRecords(history.records); setCursor(history.next_cursor) } })
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(message(err)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [days, refresh])
  function reset() { setLoading(true); setMetrics(null); setRecords([]); setCursor(null); setError('') }
  async function more() {
    if (!cursor || moreLoading) return
    setMoreLoading(true); setError('')
    try {
      const result = await auditRequest<AuditHistory>(`/reviews/history/lumadesk?cursor=${encodeURIComponent(cursor)}`)
      setRecords((previous) => [...previous, ...result.records.filter((record) => !previous.some((item) => item.review_run_id === record.review_run_id))])
      setCursor(result.next_cursor)
    } catch (err) { setError(message(err)) } finally { setMoreLoading(false) }
  }
  return <div className="page-stack">
    <header className="page-heading page-heading-row"><div><p className="eyebrow">Shared audit · retained reviews</p><h1>A record of every decision.</h1><p>Saved evaluated drafts, evidence snapshots and human decisions in this shared workspace.</p></div>
      <div className="decision-actions">{hasRetainedAudit() && <label className="field-label" htmlFor="analytics-days">Analytics period<select id="analytics-days" value={days} disabled={loading || moreLoading} onChange={(event) => { reset(); setDays(Number(event.target.value)) }}>{[7, 30, 90].map((value) => <option key={value} value={value}>Last {value} days</option>)}</select></label>}<button className="secondary-button" disabled={loading || moreLoading} onClick={() => { reset(); setRefresh((n) => n + 1) }}>Refresh</button></div>
    </header>
    <div className="demo-notice">{hasRetainedAudit() ? 'Visitors share new retained reviews. Encrypted evidence is retained for the configured period.' : 'Shared history stores metadata only; drafts and receipts remain in the current browser tab.'} Human decisions append events; they do not rewrite drafts or publish content. This ledger is not a cryptographically immutable compliance certificate.</div>
    {error && <p className="error-message error-box" role="alert">{error}</p>}
    {loading && <p role="status">Loading saved reviews and analytics…</p>}
    {!loading && !hasRetainedAudit() && <ReviewLedger records={records} durable={false} />}
    {metrics && <>
      <p className="muted-copy">{utc(metrics.period_start)} – {utc(metrics.period_end)} · updated {utc(metrics.generated_at)}</p>
      <section className="review-summary metrics-summary" aria-label="Review analytics"><div><span className="summary-label">Completed analyses</span><strong>{metrics.total_runs}</strong></div><div><span className="summary-label">Validated findings</span><strong>{metrics.total_findings}</strong></div><div><span className="summary-label">Human decision events</span><strong>{metrics.decision_events}</strong></div><div><span className="summary-label">Awaiting a decision</span><strong>{metrics.outcomes.pending ?? 0}</strong></div></section>
      <div className="section-topline"><h2>Retained reviews</h2><span className="muted-copy">All retained dates · independent of analytics period</span></div>
      <ReviewLedger key={refresh + ':' + days} records={records} durable />
      {cursor && <button className="secondary-button" disabled={moreLoading} onClick={() => { void more() }}>{moreLoading ? 'Loading…' : 'Load older reviews'}</button>}
      <div className="analytics-grid">
        <section className="review-panel"><h2>Latest outcomes</h2><div className="history-stats">{Object.entries(metrics.outcomes).map(([outcome, count]) => <span key={outcome}>{outcome}: <strong>{count}</strong></span>)}</div><p className="muted-copy">Each retained completed analysis in the period counts once. Corrections update its latest outcome and preserve earlier events.</p></section>
        <section className="review-panel"><h2>Finding categories</h2>{Object.keys(metrics.categories).length ? <div className="history-stats">{Object.entries(metrics.categories).map(([category, count]) => <span key={category}>{category.replaceAll('_', ' ')}: <strong>{count}</strong></span>)}</div> : <p className="muted-copy">No validated findings in this period.</p>}</section>
        <section className="review-panel"><h2>Most frequent rules</h2><p className="muted-copy">Up to 100 rule/version pairs.</p>{metrics.repeated_rules.length ? <div className="table-scroll"><table className="audit-table"><thead><tr><th scope="col">Rule</th><th scope="col">Version</th><th scope="col">Findings</th></tr></thead><tbody>{metrics.repeated_rules.map((rule) => <tr key={rule.rule_id + ':' + rule.version}><td>{rule.rule_id}</td><td>{rule.version}</td><td>{rule.count}</td></tr>)}</tbody></table></div> : <p className="muted-copy">No rule findings in this period.</p>}</section>
        <section className="review-panel"><h2>Daily analysis totals</h2><p className="muted-copy">UTC · completed analyses in the selected period.</p>{metrics.daily.length ? <div className="table-scroll"><table className="audit-table"><thead><tr><th scope="col">Date</th><th scope="col">Analyses</th><th scope="col">Findings</th></tr></thead><tbody>{metrics.daily.map((day) => <tr key={day.date}><td>{day.date}</td><td>{day.runs}</td><td>{day.findings}</td></tr>)}</tbody></table></div> : <p className="muted-copy">No completed analyses in this period.</p>}</section>
      </div>
      <p className="muted-copy">{metrics.definition} Legacy shared reviews and static visual checks are excluded; loading history pages does not change these totals.</p>
    </>}
  </div>
}
