/**
 * Pramana API client – single source of truth for all HTTP calls to the backend.
 * Base URL is read from the VITE_API_BASE_URL environment variable; it defaults
 * to the backend dev-server address used in README startup instructions.
 */

const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

// ─── Response Types ────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  persistence: string
}

export interface DemoRuleResponse {
  rule_id: string
  version: string
  category: string
  description: string
  source_id: string
  source_version: string
}

export interface DemoConfigResponse {
  brand_id: string
  brand_name: string
  rules: DemoRuleResponse[]
}

export interface LocationResponse {
  start: number
  end: number
}

export type EvidenceStatus =
  | 'Supported'
  | 'Contradicted'
  | 'Unsupported (needs verification)'
  | 'Indeterminate (needs verification)'

export type FindingCategory =
  | 'terminology'
  | 'prohibited_phrase'
  | 'conflicting_fact'
  | 'required_disclaimer'

export interface EvidenceReceiptResponse {
  finding_id: string
  review_run_id: string
  timestamp: string
  draft_id: string
  draft_version: string
  category: FindingCategory
  flagged_text: string | null
  location: LocationResponse | null
  rule_id: string
  rule_version: string
  source_id: string
  source_version: string
  source_excerpt: string
  explanation: string
  evidence_status: EvidenceStatus
  suggested_action: string
  validation_outcome: string
}

export interface AnalyzeResponse {
  review_run_id: string
  brand_id: string
  draft_id: string
  draft_version: string
  evaluated_at: string
  persistence: string
  input_type: string
  draft_text: string
  paragraph_count?: number
  findings: EvidenceReceiptResponse[]
}

export type ReviewDecision = 'approved' | 'revision' | 'rejected'

export interface ReviewDecisionEvent {
  decision_id: string
  decision: ReviewDecision
  decided_at: string
}

export interface ReviewDecisionResponse extends ReviewDecisionEvent {
  review_run_id: string
}

export interface ReviewRunSummary {
  review_run_id: string
  brand_id: string
  draft_id: string
  draft_version: string
  evaluated_at: string
  finding_count: number
  current_decision: ReviewDecision | null
  current_decision_at: string | null
  decision_history: ReviewDecisionEvent[]
}

const CURRENT_REVIEW_KEY = 'pramana.current-review.v1'

/** Keep the current draft/result in this tab so review pages use the exact run. */
export function saveCurrentReview(analysis: AnalyzeResponse): void {
  try {
    window.sessionStorage.setItem(CURRENT_REVIEW_KEY, JSON.stringify(analysis))
  } catch {
    // The result still remains available on the Draft Workspace page.
  }
}

export function clearCurrentReview(): void {
  try {
    window.sessionStorage.removeItem(CURRENT_REVIEW_KEY)
  } catch {
    // Ignore unavailable session storage; the API remains the source of history.
  }
}

export function loadCurrentReview(): AnalyzeResponse | null {
  try {
    const stored = window.sessionStorage.getItem(CURRENT_REVIEW_KEY)
    if (!stored) return null
    const candidate = JSON.parse(stored) as Partial<AnalyzeResponse>
    if (
      typeof candidate.review_run_id !== 'string' ||
      typeof candidate.draft_text !== 'string' ||
      !Array.isArray(candidate.findings)
    ) {
      return null
    }
    return candidate as AnalyzeResponse
  } catch {
    return null
  }
}

// ─── Request Types ─────────────────────────────────────────────────────────

export interface AnalyzeRequest {
  brand_id: string
  draft_text: string
}

// ─── API Error ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  public readonly status: number
  public readonly detail: string

  constructor(
    status: number,
    detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// ─── API Functions ─────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  return handleResponse<HealthResponse>(res)
}

export async function getDemoConfig(brandId: string): Promise<DemoConfigResponse> {
  const res = await fetch(`${API_BASE}/api/demo/config/${encodeURIComponent(brandId)}`)
  return handleResponse<DemoConfigResponse>(res)
}

export async function analyzeDraft(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/reviews/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  return handleResponse<AnalyzeResponse>(res)
}

export async function analyzeDocument(brandId: string, file: File): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append('brand_id', brandId)
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/reviews/analyze-document`, {
    method: 'POST',
    body: form,
  })
  return handleResponse<AnalyzeResponse>(res)
}

export async function getReviewHistory(brandId: string): Promise<ReviewRunSummary[]> {
  const res = await fetch(`${API_BASE}/api/reviews/history/${encodeURIComponent(brandId)}`)
  return handleResponse<ReviewRunSummary[]>(res)
}

export async function submitReviewDecision(
  reviewRunId: string,
  decision: ReviewDecision,
): Promise<ReviewDecisionResponse> {
  const res = await fetch(`${API_BASE}/api/reviews/${encodeURIComponent(reviewRunId)}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision }),
  })
  return handleResponse<ReviewDecisionResponse>(res)
}
