import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { stripTypeScriptTypes } from 'node:module'
const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const javascript = stripTypeScriptTypes(source, { mode: 'strip' }).replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify('https://pramana.test'))
const api = await import('data:text/javascript;base64,' + Buffer.from(javascript).toString('base64'))
const storage = new Map()
globalThis.window = { sessionStorage: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) } }
const originalFetch = globalThis.fetch
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => { storage.clear(); globalThis.fetch = originalFetch })
async function readiness(audit) { globalThis.fetch = async () => json({ status: 'ok', audit }); await api.getReadiness() }

test('API address trims environment whitespace before removing trailing slashes', async () => {
  const configured = stripTypeScriptTypes(source, { mode: 'strip' })
    .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify('  https://pramana.test/\n'))
  const client = await import('data:text/javascript;base64,' + Buffer.from(configured).toString('base64'))
  globalThis.fetch = async (url) => { assert.equal(url, 'https://pramana.test/health'); return json({ status: 'ok' }) }
  assert.equal((await client.getHealth()).status, 'ok')
})

test('a whitespace-padded slash preserves same-origin API requests', async () => {
  const configured = stripTypeScriptTypes(source, { mode: 'strip' })
    .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify(' /\n'))
  const client = await import('data:text/javascript;base64,' + Buffer.from(configured).toString('base64'))
  globalThis.fetch = async (url) => { assert.equal(url, '/ready'); return json({ status: 'ok', audit: false }) }
  await client.getReadiness()
})

test('fresh visitor initializes with one readiness request and no credentials', async () => {
  const calls = []
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return json({ status: 'ok', audit: false }) }
  await api.getReadiness()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'https://pramana.test/ready')
  assert.equal(calls[0].options.credentials, 'omit')
})
test('plain text analysis uses the public endpoint and exact Unicode draft', async () => {
  await readiness(false)
  const draft = 'Our dashboard \u{1f642} \u0915\u0948\u0938\u093e \u0939\u0948'
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'https://pramana.test/api/reviews/analyze')
    assert.equal(JSON.parse(options.body).draft_text, draft)
    assert.equal(options.credentials, 'omit')
    return json({ draft_text: draft })
  }
  assert.equal((await api.analyzeDraft({ brand_id: 'lumadesk', draft_text: draft })).draft_text, draft)
})
test('retained analysis preserves idempotency without identity headers', async () => {
  await readiness(true)
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'https://pramana.test/api/audit/reviews/analyze')
    assert.equal(options.headers.get('Idempotency-Key'), 'fixed-request-key')
    assert.equal(options.headers.get('Authorization'), null)
    return json({ findings: [] })
  }
  await api.analyzeDraft({ brand_id: 'lumadesk', draft_text: 'dashboard' }, 'fixed-request-key')
})
test('explicit human decision keeps expected revision in retained mode', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'https://pramana.test/api/audit/reviews/run-1/decision')
    assert.deepEqual(JSON.parse(options.body), { decision: 'revision', expected_revision: 2 })
    return json({ decision: 'revision', revision: 3 })
  }
  assert.equal((await api.submitReviewDecision('run-1', 'revision', { persistence: 'mongodb_encrypted_audit' }, 2)).revision, 3)
})
test('metadata-mode decisions and history require no account', async () => {
  await readiness(false)
  globalThis.fetch = async (url, options) => {
    if (options.method === 'POST') { assert.equal(url, 'https://pramana.test/api/reviews/run-1/decision'); return json({ decision: 'approved' }) }
    assert.equal(url, 'https://pramana.test/api/reviews/history/lumadesk'); return json([])
  }
  assert.equal((await api.submitReviewDecision('run-1', 'approved')).decision, 'approved')
  assert.deepEqual(await api.getReviewHistory('lumadesk'), [])
})
test('exact evaluated draft and receipts survive tab storage with no session', () => {
  const analysis = { review_run_id: 'run-1', draft_text: '\u{1f642} dashboard', findings: [{ location: { start: 2, end: 11 }, source_version: 'v1' }] }
  api.saveCurrentReview(analysis)
  assert.deepEqual(api.loadCurrentReview(), analysis)
  api.clearCurrentReview(); assert.equal(api.loadCurrentReview(), null)
})
test('old account storage is never restored into the public workspace', () => {
  storage.set('pramana.current-review.v1', JSON.stringify({ review_run_id: 'private-run', draft_text: 'old', findings: [] }))
  assert.equal(api.loadCurrentReview(), null)
})
test('extraction capability survives and guards public PDF decisions', async () => {
  await readiness(false)
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/api/intake')) return json({ extraction_id: 'file-1', access_token: 'file-capability', expires_at: new Date(Date.now() + 60000).toISOString() })
    assert.equal(options.headers.Authorization, 'Bearer file-capability')
    return json({ review_run_id: 'run-1', decision: 'revision' })
  }
  await api.createExtraction('lumadesk', new File(['file'], 'draft.pdf', { type: 'application/pdf' }))
  const review = { document_provenance: { extraction_id: 'file-1' } }
  assert.equal((await api.submitReviewDecision('run-1', 'revision', review)).decision, 'revision')
})
test('extraction review expires without changing retained snapshots', () => {
  const review = { review_run_id: 'run-1', draft_text: 'dashboard', findings: [], document_provenance: { original_available_until: '2000-01-01T00:00:00Z' } }
  api.saveCurrentReview(review); assert.equal(api.loadCurrentReview(), null)
  api.saveCurrentReview({ ...review, persistence: 'mongodb_encrypted_audit' }); assert.equal(api.loadCurrentReview().draft_text, 'dashboard')
})
test('service and extraction errors remain visible', async () => {
  globalThis.fetch = async () => json({ detail: 'Storage unavailable.' }, 503)
  await assert.rejects(api.getReadiness(), (error) => error.status === 503 && error.detail === 'Storage unavailable.')
  await assert.rejects(api.intakeRequest('missing'), (error) => error.status === 410)
})
test('visual input is transmitted inert and unchanged without an auth request', async () => {
  const request = { html: '<script>neverExecute()</script>', css: 'p {color: #111}', assets: [] }
  globalThis.fetch = async (url, options) => { assert.equal(url, 'https://pramana.test/api/visual/analyze'); assert.equal(options.body, JSON.stringify(request)); return json({ findings: [] }) }
  assert.deepEqual(await api.analyzeVisual(request), { findings: [] })
})
