import type { EvidenceReceiptResponse } from '../api/client'
import { CategoryBadge, EvidenceStatusBadge } from './StatusBadge'

interface FindingCardProps {
  finding: EvidenceReceiptResponse
  /** If true the card shows full detail (Evidence Receipts view). */
  expanded?: boolean
}

export function FindingCard({ finding, expanded = false }: FindingCardProps) {
  const categoryLabels: Record<string, string> = {
    terminology: 'Terminology',
    prohibited_phrase: 'Prohibited Phrase',
    conflicting_fact: 'Conflicting Fact',
    required_disclaimer: 'Required Disclaimer',
  }

  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid rgba(77, 141, 186, 0.18)',
        borderRadius: '0.75rem',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        boxShadow: '0 1px 3px rgba(10, 42, 58, 0.04)',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '13px',
              fontWeight: 500,
              color: '#19648f',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            {categoryLabels[finding.category] ?? finding.category}
          </span>
          <h3
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '18px',
              fontWeight: 600,
              color: '#004967',
              margin: 0,
              lineHeight: '24px',
            }}
          >
            {finding.rule_id.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          </h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
          <EvidenceStatusBadge status={finding.evidence_status} />
          <CategoryBadge category={finding.category} />
        </div>
      </div>

      {/* Flagged text */}
      {finding.flagged_text && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '0.5rem',
            backgroundColor: '#fdedc2',
            border: '1px solid rgba(77, 141, 186, 0.15)',
            fontFamily: 'var(--font-sans)',
            fontSize: '15px',
            color: '#221b02',
          }}
        >
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 500, color: '#40484e', display: 'block', marginBottom: '4px' }}>
            Flagged text:
          </span>
          <em>"{finding.flagged_text}"</em>
        </div>
      )}

      {/* Explanation */}
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', lineHeight: '18px', color: '#40484e', margin: 0 }}>
        {finding.explanation}
      </p>

      {/* Suggested action */}
      <div
        style={{
          padding: '0.75rem 1rem',
          borderRadius: '0.5rem',
          backgroundColor: 'rgba(202, 230, 255, 0.25)',
          border: '1px solid rgba(77, 141, 186, 0.2)',
        }}
      >
        <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 500, color: '#004967', display: 'block', marginBottom: '4px' }}>
          Suggested action
        </span>
        <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', lineHeight: '18px', color: '#221b02', margin: 0 }}>
          {finding.suggested_action}
        </p>
      </div>

      {/* Expanded: show evidence provenance */}
      {expanded && (
        <details>
          <summary
            style={{
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
              fontSize: '13px',
              fontWeight: 500,
              color: '#19648f',
              listStyle: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>receipt_long</span>
            Evidence provenance
          </summary>
          <div
            style={{
              marginTop: '0.75rem',
              padding: '0.75rem 1rem',
              borderRadius: '0.5rem',
              backgroundColor: '#fff8f0',
              border: '1px solid rgba(77, 141, 186, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <Row label="Finding ID" value={finding.finding_id} mono />
            <Row label="Review Run" value={finding.review_run_id} mono />
            <Row label="Draft" value={`${finding.draft_id} @ ${finding.draft_version}`} mono />
            {finding.location && (
              <Row label="Draft span" value={`Characters ${finding.location.start}–${finding.location.end}`} mono />
            )}
            <Row label="Rule" value={`${finding.rule_id} @ ${finding.rule_version}`} />
            <Row label="Source" value={`${finding.source_id} @ ${finding.source_version}`} />
            <Row label="Excerpt" value={finding.source_excerpt} />
            <Row label="Validation" value={finding.validation_outcome} />
            <Row label="Timestamp" value={new Date(finding.timestamp).toLocaleString()} />
          </div>
        </details>
      )}
    </div>
  )
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', fontWeight: 500, color: '#40484e', minWidth: '7rem', flexShrink: 0 }}>
        {label}:
      </span>
      <span
        style={{
          fontFamily: mono ? 'monospace' : 'var(--font-sans)',
          fontSize: '12px',
          color: '#221b02',
          wordBreak: 'break-all',
        }}
      >
        {value}
      </span>
    </div>
  )
}
