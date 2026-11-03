import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'

// Exercise the real orchestration while replacing only external SDK/API calls.
const source = stripTypeScriptTypes(await readFile(new URL('../src/auth/firebase.ts', import.meta.url), 'utf8'), { mode: 'strip' })
  .replace(/import\s+\{[\s\S]*?\}\s+from\s+'[^']+'\s*/g, '')
  .replaceAll('import.meta.env.', 'globalThis.authFixture.env.')
const names = ['getApp', 'getApps', 'initializeApp', 'browserPopupRedirectResolver', 'browserSessionPersistence',
  'createUserWithEmailAndPassword', 'initializeAuth', 'getRedirectResult', 'GithubAuthProvider', 'GoogleAuthProvider',
  'inMemoryPersistence', 'sendEmailVerification', 'sendPasswordResetEmail', 'setPersistence', 'signInWithEmailAndPassword',
  'signInWithPopup', 'signInWithRedirect', 'signOut', 'validatePassword', 'apiFetch', 'exchangeIdentity']
let serial = 0
async function fixture(options = {}) {
  const calls = []
  const storage = new Map(options.pending ? [['pramana.oauth.pending', '1']] : [])
  globalThis.window = { sessionStorage: { getItem: (k) => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) } }
  const user = { emailVerified: options.verified !== false, getIdToken: async (force) => { calls.push(['token', force]); return 'fixture-id-token' } }
  class Provider {
    setCustomParameters(value) { calls.push(['parameters', value]) }
    addScope(value) { calls.push(['scope', value]) }
  }
  const services = {
    getApps: () => [], getApp: () => ({}), initializeApp: (value) => { calls.push(['app', value]); return {} },
    initializeAuth: (_, settings) => { calls.push(['persistence', settings.persistence]); return {} },
    browserPopupRedirectResolver: 'resolver', browserSessionPersistence: 'session', inMemoryPersistence: 'memory',
    GoogleAuthProvider: Provider, GithubAuthProvider: Provider,
    validatePassword: async () => ({ isValid: options.strong !== false }),
    createUserWithEmailAndPassword: async (_, email, password) => { calls.push(['signup', email, password]); return { user } },
    signInWithEmailAndPassword: async (_, email, password) => { calls.push(['login', email, password]); if (options.invalid) throw { code: 'auth/invalid-credential' }; return { user } },
    sendEmailVerification: async () => { calls.push(['verification']) },
    sendPasswordResetEmail: async (_, email) => { calls.push(['reset', email]); if (options.unknown) throw { code: 'auth/user-not-found' } },
    setPersistence: async (_, value) => { calls.push(['persistence', value]) },
    signInWithPopup: async () => { calls.push(['popup']); return { user } },
    signInWithRedirect: async () => { calls.push(['redirect']); if (options.redirectFailure) throw { code: 'auth/network-request-failed' } },
    getRedirectResult: async () => { calls.push(['redirectResult']); return options.cancelled ? null : { user } },
    signOut: async () => { calls.push(['signout']) },
    apiFetch: async () => new Response(JSON.stringify({ configured: !options.unconfigured, project_id: options.wrongProject ? 'other' : 'fixture-project' })),
    exchangeIdentity: async (token) => { calls.push(['exchange', token]); return { actor_id: 'server-actor' } },
  }
  globalThis.authFixture = { services, env: {
    VITE_FIREBASE_API_KEY: 'public-test-key', VITE_FIREBASE_AUTH_DOMAIN: 'fixture-project.firebaseapp.com',
    VITE_FIREBASE_PROJECT_ID: 'fixture-project', VITE_FIREBASE_APP_ID: 'test-app',
  } }
  const javascript = `const { ${names.join(',')} } = globalThis.authFixture.services;\n${source}\n// fixture ${serial++}`
  const auth = await import('data:text/javascript;base64,' + Buffer.from(javascript).toString('base64'))
  return { auth, calls, storage }
}

test('signup follows provider password policy and sends verification without starting a session', async () => {
  const { auth, calls } = await fixture()
  await auth.emailSignUp('fixture@example.test', 'fictional-password')
  assert.ok(calls.some(([name]) => name === 'verification'))
  assert.ok(calls.some(([name]) => name === 'signout'))
  assert.ok(!calls.some(([name]) => name === 'exchange'))
  assert.deepEqual(calls.find(([name]) => name === 'persistence'), ['persistence', 'memory'])
})
test('unverified email cannot establish a backend session', async () => {
  const { auth, calls } = await fixture({ verified: false })
  await assert.rejects(auth.emailSignIn('fixture@example.test', 'fictional'), /Verify your email/)
  assert.ok(!calls.some(([name]) => name === 'exchange'))
  assert.equal(calls.at(-1)[0], 'signout')
})
test('verified login exchanges only the token and clears the client SDK session', async () => {
  const { auth, calls } = await fixture()
  assert.deepEqual(await auth.emailSignIn('fixture@example.test', 'fictional'), { actor_id: 'server-actor' })
  assert.deepEqual(calls.find(([name]) => name === 'exchange'), ['exchange', 'fixture-id-token'])
  assert.equal(calls.at(-1)[0], 'signout')
})
test('password reset does not reveal an unregistered email', async () => {
  const { auth } = await fixture({ unknown: true })
  await auth.resetPassword('unregistered@example.test')
  assert.equal(auth.signInError({ code: 'auth/user-not-found' }), auth.signInError({ code: 'auth/wrong-password' }))
})
test('Google popup and GitHub redirect use supported provider transactions', async () => {
  const { auth, calls, storage } = await fixture()
  await auth.socialSignIn('google')
  assert.deepEqual(calls.find(([name]) => name === 'parameters'), ['parameters', { prompt: 'select_account' }])
  await auth.socialSignIn('github', true)
  assert.deepEqual(calls.find(([name]) => name === 'scope'), ['scope', 'user:email'])
  assert.equal(storage.get('pramana.oauth.pending'), '1')
  assert.ok(calls.some(([name, value]) => name === 'persistence' && value === 'session'))
})
test('redirect restoration exchanges a verified user then removes temporary SDK persistence', async () => {
  const { auth, calls, storage } = await fixture({ pending: true })
  await auth.finishRedirect()
  assert.deepEqual(calls.find(([name]) => name === 'persistence'), ['persistence', 'session'])
  assert.equal(storage.get('pramana.oauth.pending'), undefined)
  assert.deepEqual(calls.at(-1), ['persistence', 'memory'])
})
test('failed and cancelled redirects clean up and never establish sessions', async () => {
  const failed = await fixture({ redirectFailure: true })
  await assert.rejects(failed.auth.socialSignIn('github', true))
  assert.equal(failed.storage.get('pramana.oauth.pending'), undefined)
  const cancelled = await fixture({ pending: true, cancelled: true })
  await assert.rejects(cancelled.auth.finishRedirect(), /did not finish/)
  assert.equal(cancelled.storage.get('pramana.oauth.pending'), undefined)
  assert.ok(!cancelled.calls.some(([name]) => name === 'exchange'))
})
test('missing or mismatched backend configuration fails before provider sign-in', async () => {
  for (const options of [{ unconfigured: true }, { wrongProject: true }]) {
    const { auth, calls } = await fixture(options)
    await assert.rejects(auth.emailSignIn('fixture@example.test', 'fictional'), /configuration/)
    assert.ok(!calls.some(([name]) => name === 'login'))
  }
})
test('provider collisions give original-method guidance and do not attempt account linking', async () => {
  const { auth } = await fixture()
  assert.match(auth.signInError({ code: 'auth/account-exists-with-different-credential' }), /original sign-in method/)
  assert.equal(/linkWith|fetchSignInMethodsForEmail/.test(source), false)
})

test('invalid credentials never call the backend exchange', async () => {
  const { auth, calls } = await fixture({ invalid: true })
  await assert.rejects(auth.emailSignIn('fixture@example.test', 'fictional'), (error) => error.code === 'auth/invalid-credential')
  assert.ok(!calls.some(([name]) => name === 'exchange'))
})
