export function GuidePage() {
  return <div className="page-stack">
    <header className="page-heading"><p className="eyebrow">A short guide to Pramana</p><h1>From first draft to final decision.</h1><p>A deliberate review process, with evidence at every step.</p></header>
    <div className="guide-grid">
      <article className="review-panel"><h2>Bring your manuscript</h2><p className="muted-copy">Paste text or import an ordinary-paragraph DOCX. Configured PDF/image intake extracts text locally, shows page previews and requires you to confirm the transcription. Corrections create a new version.</p><a href="#/draft-workspace">Open Draft Studio →</a></article>
      <article className="review-panel"><h2>Read the evidence</h2><p className="muted-copy">Findings refer to the exact evaluated draft and version-pinned source. Inspect quotes, spans, source excerpts and provenance. Unsupported (needs verification) means verification is needed; it does not mean false.</p><a href="#/evidence-receipts">Inspect evidence →</a></article>
      <article className="review-panel"><h2>Make a human decision</h2><p className="muted-copy">Read the draft and findings, attest that you reviewed them, then approve, request revision or reject. Suggestions never rewrite your draft. Decisions never publish content.</p><a href="#/review-and-sign-off">Go to Human Review →</a></article>
      <article className="review-panel"><h2>Keep a review record</h2><p className="muted-copy">Connect an administrator-issued organization key before analysis to save encrypted audit snapshots and decision events. Shared demo history retains metadata only. Your role controls which audit actions are permitted.</p><a href="#/reviewer-access">Connect reviewer access →</a></article>
    </div>
    <div className="demo-notice">Pramana checks configured brand rules. It is not a general fact checker, legal certification or publishing service. Static visual checks inspect supplied HTML/CSS declarations; rendered-page and full accessibility certification are unavailable.</div>
  </div>
}
