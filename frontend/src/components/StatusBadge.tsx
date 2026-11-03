import { CATEGORY_LABELS } from '../reviewLabels'
import type { EvidenceStatus, FindingCategory } from '../api/client'

const STATUS_CLASS: Record<EvidenceStatus, string> = {
  Supported: 'status-supported',
  Contradicted: 'status-contradicted',
  'Unsupported (needs verification)': 'status-unverified',
  'Indeterminate (needs verification)': 'status-unverified',
}
export function EvidenceStatusBadge({ status }: { status: EvidenceStatus }) {
  return <span className={`evidence-status ${STATUS_CLASS[status]}`}><span className="status-dot" />{status}</span>
}
export function CategoryBadge({ category }: { category: FindingCategory }) {
  return <span className="category-badge">{CATEGORY_LABELS[category]}</span>
}
