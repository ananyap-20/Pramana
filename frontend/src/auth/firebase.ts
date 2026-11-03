import { getApp, getApps, initializeApp } from 'firebase/app'
import {
  browserPopupRedirectResolver, browserSessionPersistence, createUserWithEmailAndPassword, initializeAuth, getRedirectResult,
  GithubAuthProvider, GoogleAuthProvider, inMemoryPersistence, sendEmailVerification,
  sendPasswordResetEmail, setPersistence, signInWithEmailAndPassword, signInWithPopup,
  signInWithRedirect, signOut, validatePassword, type User,
} from 'firebase/auth'
import { apiFetch, exchangeIdentity } from '../api/client'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string,
}
let ready: ReturnType<typeof prepare> | undefined
async function prepare() {
  if (Object.values(config).some((value) => !value)) throw new Error('Sign-in is awaiting configuration. Contact the operator.')
  const response = await apiFetch('/api/auth/config')
  if (!response.ok) throw new Error('The sign-in service is unavailable. Retry later.')
  const backend = await response.json() as { configured: boolean; project_id: string }
  if (!backend.configured || backend.project_id !== config.projectId) throw new Error('Sign-in configuration is incomplete. Contact the operator.')
  const app = getApps().length ? getApp() : initializeApp(config)
  const auth = initializeAuth(app, {
    persistence: window.sessionStorage.getItem('pramana.oauth.pending') === '1' ? browserSessionPersistence : inMemoryPersistence,
    popupRedirectResolver: browserPopupRedirectResolver,
  })
  return auth
}
async function client() { ready ??= prepare(); try { return await ready } catch (error) { ready = undefined; throw error } }

async function finish(user: User) {
  const auth = await client()
  try {
    if (!user.emailVerified) {
      await sendEmailVerification(user)
      throw new Error('Verify your email using the link in your inbox, then sign in again. Check spam if needed.')
    }
    return await exchangeIdentity(await user.getIdToken(true))
  } finally { await signOut(auth) }
}

export async function emailSignIn(email: string, password: string) {
  const auth = await client()
  const result = await signInWithEmailAndPassword(auth, email, password)
  return finish(result.user)
}
export async function emailSignUp(email: string, password: string) {
  const auth = await client()
  const policy = await validatePassword(auth, password)
  if (!policy.isValid) throw new Error('Choose a stronger password that meets the configured password policy.')
  const result = await createUserWithEmailAndPassword(auth, email, password)
  try { await sendEmailVerification(result.user) } finally { await signOut(auth) }
}
export async function resetPassword(email: string) {
  const auth = await client()
  try { await sendPasswordResetEmail(auth, email) }
  catch (error) {
    if ((error as { code?: string }).code !== 'auth/user-not-found') throw error
  }
}

export async function socialSignIn(name: 'google' | 'github', redirect = false) {
  const auth = await client()
  const provider = name === 'google' ? new GoogleAuthProvider() : new GithubAuthProvider()
  if (name === 'google') provider.setCustomParameters({ prompt: 'select_account' })
  else provider.addScope('user:email')
  if (redirect) {
    // Only the SDK's OAuth transaction temporarily uses tab-scoped persistence.
    // The SDK validates state and redirects to its configured authorized handler.
    await setPersistence(auth, browserSessionPersistence)
    window.sessionStorage.setItem('pramana.oauth.pending', '1')
    try { await signInWithRedirect(auth, provider) }
    catch (error) {
      window.sessionStorage.removeItem('pramana.oauth.pending')
      await signOut(auth)
      await setPersistence(auth, inMemoryPersistence)
      throw error
    }
    return null
  }
  try { return await finish((await signInWithPopup(auth, provider)).user) }
  finally { await signOut(auth) }
}

export async function finishRedirect() {
  if (window.sessionStorage.getItem('pramana.oauth.pending') !== '1') return null
  const auth = await client()
  try {
    const result = await getRedirectResult(auth)
    if (!result) throw new Error('Sign-in did not finish. Try again, or use the popup option.')
    return await finish(result.user)
  } finally { window.sessionStorage.removeItem('pramana.oauth.pending'); await signOut(auth); await setPersistence(auth, inMemoryPersistence) }
}

export function signInError(error: unknown, signup = false): string {
  if (error instanceof TypeError) return 'Could not reach the sign-in service. Check your connection and retry.'
  const code = (error as { code?: string }).code
  if (code === 'auth/popup-blocked') return 'Your browser blocked the sign-in popup. Use the redirect option below.'
  if (code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request') return 'Sign-in was cancelled. You can try again.'
  if (code === 'auth/too-many-requests') return 'Too many attempts. Wait a few minutes before trying again.'
  if (code === 'auth/network-request-failed') return 'Could not reach the sign-in service. Check your connection and retry.'
  if (code === 'auth/account-exists-with-different-credential' || code === 'auth/credential-already-in-use') return 'Use your original sign-in method. Accounts are not linked automatically by this app.'
  if (code) return signup ? 'Could not create an account. Check your details; if already registered, sign in or reset your password.' : 'Could not sign in. Check your details or use your original sign-in method.'
  return error instanceof Error ? error.message : 'Sign-in could not be completed. Please retry.'
}
