import { loadCurrentReview } from '../api/client'
import { FindingCard } from '../components/FindingCard'

export function EvidenceReceiptsPage() {
  const review = loadCurrentReview()

  return (
    <div className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">LumaDesk · fictional demo brand</p>
        <h1>Evidence receipts</h1>
        <p>Receipts from the active analysis run, with draft positions and the approved rule/source excerpt.</p>
      </header>

      {!review ? (
        <section className="empty-state">
          <h2>No active analysis</h2>
          <p>Analyze a draft first. Receipts are tied to one exact review run and draft version.</p>
          <button className="primary-button" onClick={() => { window.location.hash = '#/draft-workspace' }}>
            Go to draft workspace
          </button>
        </section>
      ) : (
        <>
          <section className="review-summary" aria-label="Receipt run summary">
            <div><span className="summary-label">Review run</span><code>{review.review_run_id}</code></div>
            <div><span className="summary-label">Draft version</span><strong>{review.draft_version}</strong></div>
            <div><span className="summary-label">Validated findings</span><strong>{review.findings.length}</strong></div>
          </section>

          {review.findings.length === 0 ? (
            <section className="empty-state">
              <h2>No findings returned</h2>
              <p>The four seeded checks found no matching issue. This result is limited to those rules and does not establish general compliance.</p>
            </section>
          ) : (
            <div className="receipt-list">
              {review.findings.map((finding) => (
                <article className="receipt-item" key={finding.finding_id}>
                  <FindingCard finding={finding} expanded />
                  {finding.location ? (
                    <DraftContext draftText={review.draft_text} start={finding.location.start} end={finding.location.end} />
                  ) : (
                    <div className="draft-context absence-context">
                      <strong>Absence check</strong>
                      <span>The required disclaimer was not present in the evaluated draft.</span>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function DraftContext({ draftText, start, end }: { draftText: string; start: number; end: number }) {
  const contextStart = Math.max(0, start - 70)
  const contextEnd = Math.min(draftText.length, end + 70)
  const before = draftText.slice(contextStart, start)
  const quote = draftText.slice(start, end)
  const after = draftText.slice(end, contextEnd)

  return (
    <div className="draft-context">
      <div className="draft-context-heading">
        <strong>Exact draft passage</strong>
        <span>Characters {start}–{end}</span>
      </div>
      <p>
        {contextStart > 0 ? '…' : ''}{before}<mark>{quote}</mark>{after}{contextEnd < draftText.length ? '…' : ''}
      </p>
    </div>
  )
}
