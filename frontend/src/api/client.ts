/**
 * Pramana API client – single source of truth for all HTTP calls to the backend.
 * Base URL is read from the VITE_API_BASE_URL environment variable; it defaults
 * to the backend dev-server address used in README startup instructions.
 */

const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

export interface SessionIdentity {
  actor_id: string
  organization_id: string
  role: 'reader' | 'reviewer' | 'admin'
  email: string
  expires_at: number
  workspace: 'personal' | 'organization'
}
let sessionIdentity: SessionIdentity | null = null
let sessionEpoch = 0
const responseEpochs = new WeakMap<Response, number>()
function checkResponseSession(response: Response) {
  const epoch = responseEpochs.get(response)
  if (epoch !== undefined && epoch !== sessionEpoch) throw new ApiError(409, 'The account changed. Retry from your current workspace.')
}
export function currentIdentity() { return sessionIdentity }

export function setSessionIdentity(identity: SessionIdentity | null) {
  const owner = identity ? `${identity.actor_id}:${identity.organization_id}` : ''
  const previousOwner = sessionIdentity ? `${sessionIdentity.actor_id}:${sessionIdentity.organization_id}` : ''
  if (owner !== previousOwner || !identity) sessionEpoch++
  if (!owner || owner !== previousOwner) intakeTokens.clear()
  try {
    if (!owner || window.sessionStorage.getItem('pramana.identity-owner.v1') !== owner) {
      clearCurrentReview()
      intakeTokens.clear()
      window.sessionStorage.removeItem(INTAKE_ACCESS_KEY)
    }
    window.sessionStorage.removeItem('pramana.audit-access.v1')
    if (owner) window.sessionStorage.setItem('pramana.identity-owner.v1', owner)
    else window.sessionStorage.removeItem('pramana.identity-owner.v1')
  } catch { /* Browser storage may be unavailable. Server authorization remains authoritative. */ }
  sessionIdentity = identity
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const epoch = sessionEpoch
  const headers = new Headers(options.headers)
  const method = options.method ?? 'GET'
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = await fetch(`${API_BASE}/api/auth/csrf`, { credentials: 'include', cache: 'no-store', signal: options.signal })
    const body = await handleResponse<{ csrf_token: string }>(csrf)
    headers.set('X-CSRF-Token', body.csrf_token)
  }
  if (epoch !== sessionEpoch) throw new ApiError(409, 'The account changed. Retry from your current workspace.')
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include', cache: 'no-store' })
  if (epoch !== sessionEpoch) throw new ApiError(409, 'The account changed. Retry from your current workspace.')
  const context = response.headers.get('X-Pramana-Context')
  if (context && sessionIdentity && context !== `${sessionIdentity.actor_id}:${sessionIdentity.organization_id}`) {
    setSessionIdentity(null)
    window.dispatchEvent(new Event('pramana:session-expired'))
    throw new ApiError(409, 'Your workspace changed in another tab. Sign in again to continue.')
  }
  if (response.status === 401 && path !== '/api/auth/session') {
    setSessionIdentity(null)
    window.dispatchEvent(new Event('pramana:session-expired'))
  }
  if (response.ok) responseEpochs.set(response, epoch)
  return response
}

export async function restoreSession(): Promise<SessionIdentity | null> {
  const epoch = sessionEpoch
  const response = await apiFetch('/api/auth/session')
  if (epoch !== sessionEpoch) throw new ApiError(409, 'The account changed. Retry the session check.')
  if (response.status === 401) { setSessionIdentity(null); return null }
  const identity = await handleResponse<SessionIdentity>(response)
  setSessionIdentity(identity)
  return identity
}

export async function exchangeIdentity(idToken: string) {
  const response = await apiFetch('/api/auth/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id_token: idToken }) })
  if (!response.ok) await handleResponse(response)
  return restoreSession()
}

export async function endSession() {
  // Invalidate in-flight private responses before starting logout.
  setSessionIdentity(null)
  try {
    const response = await apiFetch('/api/auth/logout', { method: 'POST' })
    if (!response.ok) await handleResponse(response)
  } finally { setSessionIdentity(null) }
}

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
  actor_id?: string
  revision?: number
  request_id?: string
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
  revision?: number
  expires_at?: string
  actor_id?: string
  draft_sha256?: string
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
  if (!sessionIdentity) return null
  try {
    const stored = window.sessionStorage.getItem(CURRENT_REVIEW_KEY)
    if (!stored) return null
    const candidate = JSON.parse(stored) as Partial<AnalyzeResponse>
    if (candidate.persistence !== 'mongodb_encrypted_audit' && candidate.document_provenance && Date.parse(candidate.document_provenance.original_available_until) <= Date.now()) {
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
  const value = await res.json() as T
  checkResponseSession(res)
  return value
}

// ─── API Functions ─────────────────────────────────────────────────────────

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { signal, cache: 'no-store' })
  return handleResponse<HealthResponse>(res)
}

export async function getDemoConfig(brandId: string, signal?: AbortSignal): Promise<DemoConfigResponse> {
  const res = await apiFetch(`/api/demo/config/${encodeURIComponent(brandId)}`, { signal })
  return handleResponse<DemoConfigResponse>(res)
}

export async function analyzeDraft(request: AnalyzeRequest, requestId: string = crypto.randomUUID()): Promise<AnalyzeResponse> {
  return auditRequest('/reviews/analyze', { method: 'POST', body: JSON.stringify(request) }, requestId)
}

export async function analyzeDocument(brandId: string, file: File, requestId: string = crypto.randomUUID()): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append('brand_id', brandId)
  form.append('file', file)
  return auditRequest('/reviews/analyze-document', { method: 'POST', body: form }, requestId)
}

export async function getReviewHistory(brandId: string, signal?: AbortSignal): Promise<ReviewRunSummary[]> {
  const history = await auditRequest<AuditHistory>(`/reviews/history/${encodeURIComponent(brandId)}`, { signal })
  return history.records
}

export async function submitReviewDecision(
  reviewRunId: string,
  decision: ReviewDecision,
  review?: AnalyzeResponse,
  expectedRevision?: number,
  requestId: string = crypto.randomUUID(),
): Promise<ReviewDecisionResponse> {
  if (review?.persistence === 'mongodb_encrypted_audit') {
    if (expectedRevision === undefined) throw new ApiError(409, 'Reload the review before deciding.')
    const saved = await auditRequest<ReviewDecisionEvent>(`/reviews/${encodeURIComponent(reviewRunId)}/decision`, {
      method: 'POST', body: JSON.stringify({ decision, expected_revision: expectedRevision }),
    }, requestId)
    return { ...saved, review_run_id: reviewRunId }
  }
  throw new ApiError(410, 'This legacy review is unavailable. Analyze the draft in your signed-in workspace.')
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
  confirmation: { version: number; text_sha256: string; confirmed_at: string; actor: string | null; actor_kind: string } | null
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
  actor: string | null
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
  const response = await handleResponse<ExtractionResponse & { access_token: string }>(await apiFetch('/api/intake', {
    method: 'POST', body: form, signal,
  }))
  rememberAccess(response.extraction_id, response.access_token, response.expires_at)
  return response
}

export async function intakeRequest<T>(id: string, suffix = '', body?: unknown, signal?: AbortSignal): Promise<T> {
  if (suffix === '/analyze') {
    const access = intakeHeaders(id).Authorization.replace('Bearer ', '')
    const version = body as { version: number; text_sha256: string }
    return auditRequest<T>(`/intake/${encodeURIComponent(id)}/analyze`, {
      method: 'POST', body: JSON.stringify(body), headers: { 'X-Intake-Token': access }, signal,
    }, `intake_${id}_${version.version}_${version.text_sha256}`.slice(0, 100))
  }
  return handleResponse<T>(await apiFetch(`/api/intake/${encodeURIComponent(id)}${suffix}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { ...intakeHeaders(id), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal, cache: 'no-store',
  }))
}

export async function getExtractionPreview(id: string, page: number, signal?: AbortSignal): Promise<Blob> {
  const response = await apiFetch(`/api/intake/${encodeURIComponent(id)}/pages/${page}/preview`, {
    headers: intakeHeaders(id), signal, cache: 'no-store',
  })
  if (!response.ok) await handleResponse(response)
  const value = await response.blob()
  checkResponseSession(response)
  return value
}

export async function getActiveReviewHistory(review: AnalyzeResponse): Promise<ReviewRunSummary[]> {
  if (review.persistence === 'mongodb_encrypted_audit') return [await auditRequest(`/reviews/${encodeURIComponent(review.review_run_id)}`)]
  throw new ApiError(410, 'Legacy review access is disabled.')
}

export interface AuditIdentity {
  actor_id: string
  organization_id: string
  role: 'reader' | 'reviewer' | 'admin'
  retention_days: number
}

export async function auditRequest<T>(path: string, options: RequestInit = {}, key?: string): Promise<T> {
  if (!sessionIdentity) throw new ApiError(401, 'Sign in to continue.')
  const headers = new Headers(options.headers)
  if (typeof options.body === 'string') headers.set('Content-Type', 'application/json')
  if (key) headers.set('Idempotency-Key', key)
  return handleResponse<T>(await apiFetch(`/api/audit${path}`, { ...options, headers }))
}

export async function getRetainedOriginal(runId: string): Promise<Blob> {
  if (!sessionIdentity) throw new ApiError(401, 'Sign in to download a retained original.')
  const response = await apiFetch(`/api/audit/reviews/${encodeURIComponent(runId)}/original`)
  if (!response.ok) await handleResponse(response)
  const value = await response.blob()
  checkResponseSession(response)
  return value
}

export interface AuditHistory {
  records: ReviewRunSummary[]
  next_cursor: string | null
}

export interface AuditAnalytics {
  total_runs: number
  total_findings: number
  decision_events: number
  outcomes: Record<string, number>
  categories: Record<string, number>
  repeated_rules: { rule_id: string; version: string; count: number }[]
  daily: { date: string; runs: number; findings: number }[]
  period_start: string
  period_end: string
  generated_at: string
  timezone: 'UTC'
  definition: string
}

// Mirrors backend/app/visual_models.py. Inputs remain inert; the UI never renders HTML.
export interface VisualAsset {
  asset_id: string
  media_type: 'image/png' | 'image/jpeg'
  content_base64: string
}

export interface VisualRequest {
  brand_id: string
  draft_id: string
  draft_version: string
  html: string
  css: string
  assets: VisualAsset[]
}

export interface VisualResponse {
  schema_version: '1.0'
  mode: 'static_declarations'
  brand_id: string
  draft_id: string
  draft_version: string
  input_sha256: string
  manifest_version: string
  manifest_sha256: string
  source_id: string
  source_version: string
  source_excerpt: string
  assets_sha256: Record<string, string>
  findings: {
    check: 'logo' | 'palette' | 'contrast' | 'alt_text'
    rule_version: string
    element: string
    evidence_status: EvidenceStatus
    result: string
    explanation: string
    evidence: Record<string, string | number | boolean | null>
  }[]
  limitations: string[]
}

export async function analyzeVisual(request: VisualRequest): Promise<VisualResponse> {
  const body = JSON.stringify(request)
  if (new Blob([body]).size > 768 * 1024) throw new ApiError(413, 'Visual request exceeds 768 KiB. Reduce the markup or assets.')
  return handleResponse<VisualResponse>(await apiFetch('/api/visual/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body, cache: 'no-store',
  }))
}
