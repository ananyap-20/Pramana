import type { FindingCategory } from './api/client'

export const CATEGORY_LABELS: Record<FindingCategory, string> = {
  terminology: 'Terminology', prohibited_phrase: 'Prohibited phrase',
  conflicting_fact: 'Conflicting fact', required_disclaimer: 'Required disclaimer',
}
