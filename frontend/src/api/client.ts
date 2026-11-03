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
  document_provenance?: DocumentProvenance | null
  offset_unit?: 'unicode_code_points'
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
    if (candidate.document_provenance && Date.parse(candidate.document_provenance.original_available_until) <= Date.now()) {
      clearCurrentReview()
      return null
    }
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
      detail = typeof body?.detail === 'string' ? body.detail : 'The request was invalid. Check the file and transcription limits.'
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
  review?: AnalyzeResponse,
): Promise<ReviewDecisionResponse> {
  if (review?.document_provenance) {
    return intakeRequest(review.document_provenance.extraction_id,
      `/reviews/${encodeURIComponent(reviewRunId)}/decision`, { decision })
  }
  const res = await fetch(`${API_BASE}/api/reviews/${encodeURIComponent(reviewRunId)}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision }),
  })
  return handleResponse<ReviewDecisionResponse>(res)
}

export interface ExtractedPage {
  page: number
  text: string
  start: number
  end: number
  method: 'pdf_text' | 'ocr' | 'human_edited'
  width: number
  height: number
  coordinates: 'pdf_points_bottom_left' | 'pixels_top_left' | 'none'
  rotation: number
  regions: { start: number; end: number; bounds: number[] | null; confidence: number | null }[]
  warnings: string[]
}

export interface ExtractionVersion {
  version: number
  text_sha256: string
  text: string
  pages: ExtractedPage[]
  human_edited: boolean
  parent_version: number | null
  created_at: string
}

export interface ExtractionResponse {
  extraction_id: string
  state: 'queued' | 'processing' | 'needs_confirmation' | 'ready' | 'failed' | 'expired'
  filename: string
  file_type: string
  file_sha256: string
  expires_at: string
  current: ExtractionVersion | null
  confirmation: { version: number; text_sha256: string; confirmed_at: string; actor: null; actor_kind: string } | null
  warnings: string[]
  error: string | null
  tools: Record<string, string>
  settings: Record<string, string | number>
  extraction_seconds: number | null
}

export interface DocumentProvenance {
  extraction_id: string
  file_sha256: string
  file_type: string
  version: number
  text_sha256: string
  human_edited: boolean
  confirmed_at: string
  actor: null
  actor_kind: string
  original_available_until: string
  tools: Record<string, string>
  settings: Record<string, string | number>
  pages: ExtractedPage[]
}

const intakeTokens = new Map<string, { token: string; expires: number }>()
const INTAKE_ACCESS_KEY = 'pramana.intake-access.v1'

function rememberAccess(id: string, token: string, expiresAt: string) {
  for (const [key, value] of intakeTokens) if (value.expires <= Date.now()) intakeTokens.delete(key)
  intakeTokens.set(id, { token, expires: Date.parse(expiresAt) })
  try { window.sessionStorage.setItem(INTAKE_ACCESS_KEY, JSON.stringify([...intakeTokens])) } catch { /* Memory access still works. */ }
}

function intakeHeaders(id: string): Record<string, string> {
  if (!intakeTokens.has(id)) {
    try {
      const saved = JSON.parse(window.sessionStorage.getItem(INTAKE_ACCESS_KEY) ?? '[]') as [string, { token: string; expires: number }][]
      for (const [key, value] of saved) if (value.expires > Date.now()) intakeTokens.set(key, value)
    } catch { /* Missing access is reported below. */ }
  }
  const access = intakeTokens.get(id)
  if (!access || access.expires <= Date.now()) throw new ApiError(410, 'Extraction access expired. Upload the original again.')
  return { Authorization: `Bearer ${access.token}` }
}

export async function createExtraction(brandId: string, file: File, signal?: AbortSignal): Promise<ExtractionResponse> {
  const form = new FormData()
  form.append('brand_id', brandId)
  form.append('file', file)
  const response = await handleResponse<ExtractionResponse & { access_token: string }>(await fetch(`${API_BASE}/api/intake`, {
    method: 'POST', body: form, signal,
  }))
  rememberAccess(response.extraction_id, response.access_token, response.expires_at)
  return response
}

export async function intakeRequest<T>(id: string, suffix = '', body?: unknown, signal?: AbortSignal): Promise<T> {
  return handleResponse<T>(await fetch(`${API_BASE}/api/intake/${encodeURIComponent(id)}${suffix}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { ...intakeHeaders(id), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal, cache: 'no-store',
  }))
}

export async function getExtractionPreview(id: string, page: number, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/intake/${encodeURIComponent(id)}/pages/${page}/preview`, {
    headers: intakeHeaders(id), signal, cache: 'no-store',
  })
  if (!response.ok) await handleResponse(response)
  return response.blob()
}

export async function getActiveReviewHistory(review: AnalyzeResponse): Promise<ReviewRunSummary[]> {
  if (review.document_provenance) {
    return [await intakeRequest<ReviewRunSummary>(review.document_provenance.extraction_id,
      `/reviews/${encodeURIComponent(review.review_run_id)}`)]
  }
  return getReviewHistory(review.brand_id)
}
