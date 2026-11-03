import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { stripTypeScriptTypes } from 'node:module'

// Test the real client without adding a browser test dependency or loading private .env files.
const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const javascript = stripTypeScriptTypes(source, { mode: 'strip' })
  .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify('http://pramana.test'))
const api = await import('data:text/javascript;base64,' + Buffer.from(javascript).toString('base64'))
const storage = new Map()
globalThis.window = { sessionStorage: {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
} }
const originalFetch = globalThis.fetch
afterEach(() => { storage.clear(); globalThis.fetch = originalFetch })
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

test('visual checks send exact inert input using the existing static contract', async () => {
  const request = { brand_id: 'lumadesk', draft_id: 'draft-1', draft_version: 'v2', html: '<p>नमस्ते 😀</p>', css: 'p { color: #111; }', assets: [] }
  let observed
  globalThis.fetch = async (url, options) => { observed = { url, options }; return json({ mode: 'static_declarations', findings: [] }) }
  const response = await api.analyzeVisual(request)
  assert.equal(observed.url, 'http://pramana.test/api/visual/analyze')
  assert.deepEqual(JSON.parse(observed.options.body), request)
  assert.equal(observed.options.cache, 'no-store')
  assert.equal(response.mode, 'static_declarations')
})

test('oversized visual payload is rejected before any network request', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return json({}) }
  await assert.rejects(api.analyzeVisual({ html: '😀'.repeat(200000) }), (error) => error instanceof api.ApiError && error.status === 413)
  assert.equal(calls, 0)
})

test('missing visual configuration remains an unavailable error', async () => {
  globalThis.fetch = async () => json({ detail: 'No active approved visual manifest exists for this brand.' }, 404)
  await assert.rejects(api.analyzeVisual({ html: '<p>Example</p>' }), (error) => error.status === 404 && error.detail.includes('manifest'))
})

test('health and configuration forward cancellation and avoid cached state', async () => {
  const controller = new AbortController()
  const calls = []
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return json({ status: 'ok' }) }
  await api.getHealth(controller.signal)
  await api.getDemoConfig('brand/id', controller.signal)
  await api.getReviewHistory('brand/id', controller.signal)
  assert.equal(calls[1].url, 'http://pramana.test/api/demo/config/brand%2Fid')
  assert.equal(calls[2].url, 'http://pramana.test/api/reviews/history/brand%2Fid')
  for (const call of calls) { assert.equal(call.options.signal, controller.signal); assert.equal(call.options.cache, 'no-store') }
})

test('invalid organization access never falls back to shared demo analysis', async () => {
  api.setAuditToken('fictional-test-key')
  const calls = []
  globalThis.fetch = async (url) => { calls.push(url); return json({ detail: 'Invalid access key.' }, 401) }
  await assert.rejects(api.analyzeDraft({ brand_id: 'lumadesk', draft_text: 'Private fixture' }, 'request-1'), (error) => error.status === 401)
  assert.deepEqual(calls, ['http://pramana.test/api/audit/reviews/analyze'])
})

test('human audit decisions preserve expected revision and retry identity', async () => {
  api.setAuditToken('fictional-test-key')
  let observed
  globalThis.fetch = async (url, options) => { observed = { url, options }; return json({ decision_id: 'event-1', decision: 'revision', revision: 4 }) }
  await api.submitReviewDecision('run/1', 'revision', { persistence: 'mongodb_encrypted_audit' }, 3, 'same-request-1')
  assert.equal(observed.url, 'http://pramana.test/api/audit/reviews/run%2F1/decision')
  assert.deepEqual(JSON.parse(observed.options.body), { decision: 'revision', expected_revision: 3 })
  assert.equal(observed.options.headers.get('Idempotency-Key'), 'same-request-1')
  assert.equal(observed.options.headers.get('Authorization'), 'Bearer fictional-test-key')
})

test('current review preserves exact evaluated Unicode text and receipt versions', () => {
  const review = { review_run_id: 'run-1', draft_text: 'नमस्ते 😀 dashboard', draft_version: 'v7', findings: [{ source_version: 'v2', flagged_text: 'dashboard', location: { start: 9, end: 18 } }] }
  api.saveCurrentReview(review)
  assert.deepEqual(api.loadCurrentReview(), review)
  api.clearCurrentReview()
  assert.equal(api.loadCurrentReview(), null)
})

test('expired temporary intake reviews cannot replay as active reviews', () => {
  const review = { review_run_id: 'run-1', draft_text: 'Example', findings: [], document_provenance: { original_available_until: '2000-01-01T00:00:00Z' } }
  api.saveCurrentReview(review)
  assert.equal(api.loadCurrentReview(), null)
  api.saveCurrentReview({ ...review, persistence: 'mongodb_encrypted_audit' })
  assert.equal(api.loadCurrentReview().review_run_id, 'run-1')
})

test('retained-original downloads require organization access and propagate storage errors', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return json({ detail: 'Private file storage is not configured.' }, 503) }
  await assert.rejects(api.getRetainedOriginal('run/1'), (error) => error.status === 401)
  assert.equal(calls, 0)
  api.setAuditToken('fictional-test-key')
  await assert.rejects(api.getRetainedOriginal('run/1'), (error) => error.status === 503 && error.detail.includes('storage'))
  assert.equal(calls, 1)
})
