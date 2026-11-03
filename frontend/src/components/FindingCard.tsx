import { CATEGORY_LABELS } from '../reviewLabels'
import type { EvidenceReceiptResponse } from '../api/client'
import { EvidenceStatusBadge } from './StatusBadge'

export function FindingCard({ finding, expanded = false }: { finding: EvidenceReceiptResponse; expanded?: boolean }) {
  return <article className="finding-card">
    <div className="finding-header"><div><span className="eyebrow">{CATEGORY_LABELS[finding.category]}</span><h3>{finding.rule_id.replace(/-/g, ' ')}</h3></div><EvidenceStatusBadge status={finding.evidence_status} /></div>
    {finding.flagged_text && <blockquote className="finding-quote"><small>Exact flagged text</small>“{finding.flagged_text}”</blockquote>}
    <p>{finding.explanation}</p>
    <div className="finding-action"><strong>Suggested action · for your consideration</strong><p>{finding.suggested_action}</p></div>
    {expanded ? <details><summary>Inspect evidence provenance</summary><dl className="provenance-rows">
      <dt>Finding</dt><dd><code>{finding.finding_id}</code></dd>
      <dt>Review run</dt><dd><code>{finding.review_run_id}</code></dd>
      <dt>Exact draft</dt><dd><code>{finding.draft_id} @ {finding.draft_version}</code></dd>
      {finding.location && <><dt>Draft span</dt><dd>Characters {finding.location.start}–{finding.location.end} · Unicode code points</dd></>}
      <dt>Rule version</dt><dd>{finding.rule_id} @ {finding.rule_version}</dd>
      <dt>Source version</dt><dd>{finding.source_id} @ {finding.source_version}</dd>
      <dt>Source excerpt</dt><dd>{finding.source_excerpt}</dd>
      <dt>Validation</dt><dd>{finding.validation_outcome}</dd>
      <dt>Evaluated</dt><dd>{new Date(finding.timestamp).toLocaleString()}</dd>
    </dl></details> : <a href="#/evidence-receipts" className="text-button">Inspect source & draft passage →</a>}
  </article>
}
