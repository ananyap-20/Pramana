import { useEffect, useRef, useState } from 'react'
import { ApiError, auditRequest, saveCurrentReview, type AnalyzeResponse, type ReviewRunSummary } from '../api/client'

const decisionLabels: Record<string, string> = { approved: 'Approved', revision: 'Needs revision', rejected: 'Rejected' }
export function ReviewLedger({ records, durable }: { records: ReviewRunSummary[]; durable: boolean }) {
  const [search, setSearch] = useState('')
  const [decision, setDecision] = useState('all')
  const [selected, setSelected] = useState('')
  const [snapshot, setSnapshot] = useState<AnalyzeResponse | null>(null)
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const record = records.find((item) => item.review_run_id === selected)
  const query = search.trim().toLowerCase()
  const filtered = records.filter((item) => (decision === 'all' || (item.current_decision ?? 'pending') === decision)
    && [item.review_run_id, item.draft_id, item.actor_id ?? ''].some((value) => value.toLowerCase().includes(query)))

  async function inspect(item: ReviewRunSummary) {
    controller.current?.abort()
    setSelected(item.review_run_id); setSnapshot(null); setError('')
    if (!durable) return
    controller.current = new AbortController()
    const signal = controller.current.signal
    setOpening(true)
    try {
      const response = await auditRequest<{ analysis: AnalyzeResponse }>(`/reviews/${encodeURIComponent(item.review_run_id)}/snapshot`, { signal })
      if (!signal.aborted) setSnapshot(response.analysis)
    } catch (err) {
      if (!signal.aborted) setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not load the retained snapshot. Retry inspection.')
    } finally { if (!signal.aborted) setOpening(false) }
  }
  return <div className="ledger-layout">
    <section className="review-panel ledger" aria-label="Review ledger">
      <div className="ledger-toolbar"><label className="field-label" htmlFor="ledger-search">Search loaded records<input id="ledger-search" type="search" placeholder="Run, draft or reviewer ID" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <label className="field-label" htmlFor="ledger-decision">Human decision<select id="ledger-decision" value={decision} onChange={(event) => setDecision(event.target.value)}><option value="all">All decisions</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="revision">Needs revision</option><option value="rejected">Rejected</option></select></label></div>
      <div className="table-scroll"><table className="audit-table"><thead><tr><th scope="col">Entry & timestamp</th><th scope="col">Findings</th><th scope="col">Human decision</th><th scope="col">Actions</th></tr></thead><tbody>
        {filtered.map((item) => <tr key={item.review_run_id} className={selected === item.review_run_id ? 'is-selected' : undefined}><td><code>{item.review_run_id}</code><time dateTime={item.evaluated_at}>{new Date(item.evaluated_at).toLocaleString()}</time>{item.actor_id && <span className="muted-copy">By {item.actor_id}</span>}</td><td>{item.finding_count}<span className="muted-copy"> validated</span></td>
          <td><span className={`evidence-status ${item.current_decision === 'approved' ? 'status-supported' : item.current_decision === 'rejected' ? 'status-contradicted' : 'status-unverified'}`}>{decisionLabels[item.current_decision ?? ''] ?? 'Pending'}</span></td>
          <td><button className="secondary-button" aria-label={`Inspect review ${item.review_run_id}`} onClick={() => { void inspect(item) }}>Inspect</button></td></tr>)}
      </tbody></table></div>
      {!filtered.length && <div className="empty-state"><h3>{records.length ? 'No matching records' : 'Your ledger starts here.'}</h3><p>{records.length ? 'Change the search or decision filter to see other loaded records.' : 'Complete an analysis to create a review record.'}</p>{!records.length && <a href="#/draft-workspace" className="secondary-button">Open Draft Studio</a>}</div>}
      <p className="ledger-caption">Showing {filtered.length} of {records.length} loaded records. Search and decision filters apply to loaded records only.</p>
    </section>
    <aside className="review-panel ledger-inspector" aria-label="Review inspection">
      <p className="eyebrow">{record ? 'Selected review' : 'The inspection desk'}</p><h2>Audit snapshot</h2>
      {!record ? <p className="muted-copy">Inspect a ledger entry to view its draft version and human decision history.{durable ? ' Organization reviews also include the retained evaluated text and receipts.' : ' Shared demo history stores metadata only.'}</p> : <>
        <code>{record.review_run_id}</code><dl className="provenance-rows"><dt>Evaluated</dt><dd>{new Date(record.evaluated_at).toLocaleString()}</dd><dt>Draft</dt><dd><code>{record.draft_id} @ {record.draft_version}</code></dd><dt>Decision</dt><dd>{decisionLabels[record.current_decision ?? ''] ?? 'Pending'}</dd>
          {record.revision !== undefined && <><dt>Revision</dt><dd>{record.revision}</dd></>}
          {record.expires_at && <><dt>Retained until</dt><dd>{new Date(record.expires_at).toLocaleString()}</dd></>}
          {record.draft_sha256 && <><dt>Draft SHA-256</dt><dd><code>{record.draft_sha256}</code></dd></>}</dl>
        <h3 className="access-footnote">Human decision events</h3>
        {record.decision_history.length ? <ol className="decision-history">{record.decision_history.map((event) => <li key={event.decision_id}><strong>{decisionLabels[event.decision]}</strong><span>{event.actor_id ?? 'Demo reviewer'}{event.revision !== undefined ? ` · revision ${event.revision}` : ''}</span><time dateTime={event.decided_at}>{new Date(event.decided_at).toLocaleString()}</time></li>)}</ol> : <p className="muted-copy">No human decision recorded.</p>}
        {opening && <p role="status">Loading the saved evaluated snapshot…</p>}
        {error && <div className="error-box" role="alert"><p className="error-message">{error}</p><button className="secondary-button" onClick={() => { void inspect(record) }}>Retry inspection</button></div>}
        {snapshot && snapshot.review_run_id === record.review_run_id && <><h3 className="access-footnote">Evaluated manuscript</h3><pre className="inspector-excerpt">{snapshot.draft_text}</pre><p className="muted-copy">{snapshot.findings.length} validated findings. Opening this snapshot replaces the active review in this tab.</p><button className="primary-button" onClick={() => { saveCurrentReview(snapshot); window.location.hash = '#/review-and-sign-off' }}>Open saved review →</button></>}
        {!durable && <p className="muted-copy access-footnote">Draft text and receipts cannot be reopened from shared metadata history. Connect organization access before creating a review that needs a retained snapshot.</p>}
      </>}
    </aside>
  </div>
}
