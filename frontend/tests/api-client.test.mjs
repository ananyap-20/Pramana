import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { stripTypeScriptTypes } from 'node:module'

const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const javascript = stripTypeScriptTypes(source, { mode: 'strip' })
  .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify('https://pramana.test'))
const api = await import('data:text/javascript;base64,' + Buffer.from(javascript).toString('base64'))
const storage = new Map()
const events = []
globalThis.window = { dispatchEvent: (event) => events.push(event.type), sessionStorage: {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
} }
const originalFetch = globalThis.fetch
const identity = { actor_id: 'alice', organization_id: 'p_alice', role: 'reviewer', expires_at: Date.now() / 1000 + 3600, workspace: 'personal', email: 'fictional@example.test' }
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
function mockFetch(handler) {
  globalThis.fetch = async (url, options) => url.endsWith('/api/auth/csrf') ? json({ csrf_token: 'fictional-csrf-value' }) : handler(url, options)
}
beforeEach(() => { api.setSessionIdentity(identity); events.length = 0 })
afterEach(() => { api.setSessionIdentity(null); storage.clear(); globalThis.fetch = originalFetch })

test('visual checks send exact inert input with cookie credentials and CSRF', async () => {
  const request = { brand_id: 'lumadesk', draft_id: 'draft-1', draft_version: 'v2', html: '<p>?????? ??</p>', css: 'p { color: #111; }', assets: [] }
  let observed
  mockFetch(async (url, options) => { observed = { url, options }; return json({ mode: 'static_declarations', findings: [] }) })
  const response = await api.analyzeVisual(request)
  assert.equal(observed.url, 'https://pramana.test/api/visual/analyze')
  assert.deepEqual(JSON.parse(observed.options.body), request)
  assert.equal(observed.options.credentials, 'include')
  assert.equal(observed.options.headers.get('X-CSRF-Token'), 'fictional-csrf-value')
  assert.equal(response.mode, 'static_declarations')
})
test('oversized visual payload is rejected before network requests', async () => {
  let calls = 0
  mockFetch(async () => { calls++; return json({}) })
  await assert.rejects(api.analyzeVisual({ html: '\u{1F600}'.repeat(200000) }), (error) => error.status === 413)
  assert.equal(calls, 0)
})
test('missing visual configuration remains an unavailable error', async () => {
  mockFetch(async () => json({ detail: 'No active approved visual manifest exists for this brand.' }, 404))
  await assert.rejects(api.analyzeVisual({ html: '<p>Example</p>' }), (error) => error.status === 404 && error.detail.includes('manifest'))
})
test('configuration and private history forward cancellation and avoid cached state', async () => {
  const controller = new AbortController()
  const calls = []
  mockFetch(async (url, options) => { calls.push({ url, options }); return json(url.includes('/history/') ? { records: [] } : { status: 'ok' }) })
  await api.getHealth(controller.signal)
  await api.getDemoConfig('brand/id', controller.signal)
  await api.getReviewHistory('brand/id', controller.signal)
  assert.equal(calls[1].url, 'https://pramana.test/api/demo/config/brand%2Fid')
  assert.equal(calls[2].url, 'https://pramana.test/api/audit/reviews/history/brand%2Fid')
  for (const call of calls) { assert.equal(call.options.signal, controller.signal); assert.equal(call.options.cache, 'no-store') }
})
test('invalid sessions never fall back to shared demo analysis', async () => {
  const calls = []
  mockFetch(async (url) => { calls.push(url); return json({ detail: 'Session expired.' }, 401) })
  await assert.rejects(api.analyzeDraft({ brand_id: 'lumadesk', draft_text: 'Private fixture' }, 'request-1'), (error) => error.status === 401)
  assert.deepEqual(calls, ['https://pramana.test/api/audit/reviews/analyze'])
  assert.equal(api.currentIdentity(), null)
  assert.deepEqual(events, ['pramana:session-expired'])
})
test('human decisions preserve expected revision and retry identity without access keys', async () => {
  let observed
  mockFetch(async (url, options) => { observed = { url, options }; return json({ decision_id: 'event-1', decision: 'revision', revision: 4 }) })
  await api.submitReviewDecision('run/1', 'revision', { persistence: 'mongodb_encrypted_audit' }, 3, 'same-request-1')
  assert.equal(observed.url, 'https://pramana.test/api/audit/reviews/run%2F1/decision')
  assert.deepEqual(JSON.parse(observed.options.body), { decision: 'revision', expected_revision: 3 })
  assert.equal(observed.options.headers.get('Idempotency-Key'), 'same-request-1')
  assert.equal(observed.options.headers.get('Authorization'), null)
})
test('exact evaluated Unicode and receipt versions survive same-account session restoration', async () => {
  const review = { review_run_id: 'run-1', draft_text: '?????? ?? dashboard', draft_version: 'v7', findings: [{ source_version: 'v2', flagged_text: 'dashboard' }] }
  api.saveCurrentReview(review)
  mockFetch(async () => json(identity))
  await api.restoreSession()
  assert.deepEqual(api.loadCurrentReview(), review)
})
test('account or workspace changes clear active reviews and extraction capabilities', async () => {
  api.saveCurrentReview({ review_run_id: 'old', draft_text: 'Private fixture', findings: [] })
  storage.set('pramana.intake-access.v1', 'old-capability')
  storage.set('pramana.audit-access.v1', 'old-key')
  api.setSessionIdentity({ ...identity, actor_id: 'bob', organization_id: 'p_bob' })
  assert.equal(api.loadCurrentReview(), null)
  assert.equal(storage.get('pramana.intake-access.v1'), undefined)
  assert.equal(storage.get('pramana.audit-access.v1'), undefined)
})
test('expired extraction review cannot replay while retained authenticated review remains available', () => {
  const review = { review_run_id: 'run-1', draft_text: 'Example', findings: [], document_provenance: { original_available_until: '2000-01-01T00:00:00Z' } }
  api.saveCurrentReview(review)
  assert.equal(api.loadCurrentReview(), null)
  api.saveCurrentReview({ ...review, persistence: 'mongodb_encrypted_audit' })
  assert.equal(api.loadCurrentReview().review_run_id, 'run-1')
})
test('retained files require a session and preserve storage failures', async () => {
  api.setSessionIdentity(null)
  let calls = 0
  mockFetch(async () => { calls++; return json({ detail: 'Private file storage is not configured.' }, 503) })
  await assert.rejects(api.getRetainedOriginal('run/1'), (error) => error.status === 401)
  assert.equal(calls, 0)
  api.setSessionIdentity(identity)
  await assert.rejects(api.getRetainedOriginal('run/1'), (error) => error.status === 503)
})
test('login exchanges only the ID token, then restores the server-derived identity', async () => {
  api.setSessionIdentity(null)
  const calls = []
  mockFetch(async (url, options) => { calls.push({ url, options }); return options.method === 'POST' ? new Response(null, { status: 204 }) : json(identity) })
  assert.deepEqual(await api.exchangeIdentity('fictional-id-token'), identity)
  assert.deepEqual(JSON.parse(calls[0].options.body), { id_token: 'fictional-id-token' })
  assert.equal(calls[0].options.headers.get('X-CSRF-Token'), 'fictional-csrf-value')
  assert.equal(calls[1].url, 'https://pramana.test/api/auth/session')
})
test('logout clears local review state even when provider revocation fails', async () => {
  api.saveCurrentReview({ review_run_id: 'run', draft_text: 'Private', findings: [] })
  mockFetch(async () => json({ detail: 'Remote revocation unavailable.' }, 503))
  await assert.rejects(api.endSession(), (error) => error.status === 503)
  assert.equal(api.currentIdentity(), null)
  assert.equal(api.loadCurrentReview(), null)
})
test('in-flight responses cannot restore a previous accounts private state', async () => {
  let finish
  mockFetch(() => new Promise((resolve) => { finish = resolve }))
  const pending = api.auditRequest('/reviews/history/lumadesk')
  api.setSessionIdentity({ ...identity, actor_id: 'bob' })
  finish(json({ records: [{ review_run_id: 'alice-private' }] }))
  await assert.rejects(pending, (error) => error.status === 409)
})
test('legacy decisions never send a mutation to the public API', async () => {
  let calls = 0
  mockFetch(async () => { calls++; return json({}) })
  await assert.rejects(api.submitReviewDecision('legacy', 'approved', { persistence: 'in_memory_demo_not_durable' }), (error) => error.status === 410)
  assert.equal(calls, 0)
})

test('a response for a different cookie owner closes the stale tab session', async () => {
  mockFetch(async () => new Response(JSON.stringify({ records: [{ review_run_id: 'other-private' }] }), {
    headers: { 'Content-Type': 'application/json', 'X-Pramana-Context': 'bob:p_bob' },
  }))
  await assert.rejects(api.auditRequest('/reviews/history/lumadesk'), (error) => error.status === 409)
  assert.equal(api.currentIdentity(), null)
})

test('account changes during response-body parsing discard the private payload', async () => {
  let release
  const body = new ReadableStream({ start(controller) { release = () => {
    controller.enqueue(new TextEncoder().encode(JSON.stringify({ records: [{ review_run_id: 'private' }] })))
    controller.close()
  } } })
  mockFetch(async () => new Response(body))
  const pending = api.auditRequest('/reviews/history/lumadesk')
  await new Promise((resolve) => setTimeout(resolve, 0))
  api.setSessionIdentity({ ...identity, actor_id: 'bob' })
  release()
  await assert.rejects(pending, (error) => error.status === 409)
})
