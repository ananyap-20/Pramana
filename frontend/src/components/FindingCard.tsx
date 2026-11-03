import { CATEGORY_LABELS } from '../reviewLabels'
import type { EvidenceReceiptResponse } from '../api/client'
import { EvidenceStatusBadge } from './StatusBadge'
import { useState } from 'react'

const TITLES: Record<string, string> = {
  'preferred-terminology-workspace': 'Use the preferred term “workspace”',
  'prohibited-guaranteed-no-errors': 'Remove the absolute guarantee',
  'starter-plan-team-limit': 'Check the Starter plan team limit',
  'plan-feature-availability-disclaimer': 'Plan availability disclaimer',
}

export function FindingCard({ finding, expanded = false, collapsible = false, initiallyOpen = false }: {
  finding: EvidenceReceiptResponse; expanded?: boolean; collapsible?: boolean; initiallyOpen?: boolean
}) {
  const [open, setOpen] = useState(initiallyOpen)
  const header = <div className="finding-header"><div><span className="eyebrow">{CATEGORY_LABELS[finding.category]}</span><h3>{TITLES[finding.rule_id] ?? finding.rule_id.replace(/-/g, ' ')}</h3></div><EvidenceStatusBadge status={finding.evidence_status} /></div>
  const body = <div className="finding-body">
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
  </div>
  return collapsible ? <details className="finding-row" name="review-findings" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>{header}<span className="finding-toggle">{open ? 'Hide details −' : 'Review finding +'}</span></summary>{body}
  </details> : <article className="finding-card">{header}{body}</article>
}
