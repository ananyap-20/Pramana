import type { EvidenceStatus, FindingCategory } from '../api/client'

interface EvidenceStatusBadgeProps {
  status: EvidenceStatus
}

const STATUS_STYLES: Record<EvidenceStatus, { bg: string; color: string; border: string; icon: string }> = {
  'Supported': {
    bg: 'rgba(151, 215, 255, 0.3)',
    color: '#004967',
    border: 'rgba(77, 141, 186, 0.5)',
    icon: 'check_circle',
  },
  'Contradicted': {
    bg: '#ffdad6',
    color: '#93000a',
    border: '#ba1a1a',
    icon: 'cancel',
  },
  'Unsupported (needs verification)': {
    bg: '#f1e2b7',
    color: '#40484e',
    border: '#c0c7cf',
    icon: 'help',
  },
  'Indeterminate (needs verification)': {
    bg: '#f1e2b7',
    color: '#40484e',
    border: '#c0c7cf',
    icon: 'help_outline',
  },
}

export function EvidenceStatusBadge({ status }: EvidenceStatusBadgeProps) {
  const style = STATUS_STYLES[status]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 10px',
        borderRadius: '0.5rem',
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
        fontFamily: 'var(--font-sans)',
        fontSize: '13px',
        fontWeight: 500,
        lineHeight: '18px',
        whiteSpace: 'nowrap',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>{style.icon}</span>
      {status}
    </span>
  )
}

interface CategoryBadgeProps {
  category: FindingCategory
}

const CATEGORY_LABELS: Record<FindingCategory, string> = {
  terminology: 'Terminology',
  prohibited_phrase: 'Prohibited Phrase',
  conflicting_fact: 'Conflicting Fact',
  required_disclaimer: 'Required Disclaimer',
}

export function CategoryBadge({ category }: CategoryBadgeProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: '0.25rem',
        backgroundColor: '#f7e7bd',
        color: '#221b02',
        fontFamily: 'var(--font-sans)',
        fontSize: '13px',
        fontWeight: 500,
        lineHeight: '18px',
      }}
    >
      {CATEGORY_LABELS[category]}
    </span>
  )
}
