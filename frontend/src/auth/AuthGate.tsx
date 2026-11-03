import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ApiError, endSession, restoreSession, setSessionIdentity, type SessionIdentity } from '../api/client'
import { emailSignIn, emailSignUp, finishRedirect, resetPassword, signInError, socialSignIn } from './firebase'
import { Icon } from '../components/Icon'

// Share startup across React StrictMode's effect replay, especially OAuth redirects.
let startup: Promise<SessionIdentity | null> | undefined

export function AuthGate({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<SessionIdentity | null>(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const refresh = useCallback(async () => {
    try { setIdentity(await restoreSession()); setError('') }
    catch (err) { setIdentity(null); setSessionIdentity(null); setError(err instanceof Error ? err.message : 'Could not verify your session. Retry later.') }
  }, [])
  useEffect(() => {
    let active = true
    void (async () => {
      try {
        startup ??= finishRedirect().then((redirected) => redirected ?? restoreSession())
        const value = await startup
        if (active) { setIdentity(value); setError('') }
      } catch (err) {
        setSessionIdentity(null)
        if (active) { setIdentity(null); setError(signInError(err)) }
      } finally { if (active) setChecking(false) }
    })()
    return () => { active = false }
  }, [retry])
  useEffect(() => {
    const expired = () => { setSessionIdentity(null); setIdentity(null); setError('Your session ended. Sign in again to continue.') }
    const visible = () => { if (document.visibilityState === 'visible') void refresh() }
    window.addEventListener('pramana:session-expired', expired)
    document.addEventListener('visibilitychange', visible)
    const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('pramana-session') : null
    if (channel) channel.onmessage = () => { setSessionIdentity(null); setIdentity(null); void refresh() }
    const timer = identity ? window.setTimeout(expired, Math.max(0, identity.expires_at * 1000 - Date.now())) : undefined
    const interval = identity ? window.setInterval(() => { void refresh() }, 60_000) : undefined
    return () => {
      window.removeEventListener('pramana:session-expired', expired)
      document.removeEventListener('visibilitychange', visible)
      channel?.close(); window.clearTimeout(timer); window.clearInterval(interval)
    }
  }, [identity, refresh])
  if (checking) return <AuthFrame><p role="status">Restoring your secure session…</p></AuthFrame>
  if (identity) return <div key={`${identity.actor_id}:${identity.organization_id}`}>
    <div className="session-toolbar"><span>{identity.email || 'Signed in'} · {identity.workspace === 'personal' ? 'Personal workspace' : 'Organization workspace'} · {identity.role}</span>
      <button className="text-button" onClick={() => {
        void endSession().catch((err: unknown) => { setError(err instanceof ApiError ? err.detail : 'Could not reach the sign-out service. Retry before leaving this device.') })
          .finally(() => { setIdentity(null); if (typeof BroadcastChannel !== 'undefined') { const channel = new BroadcastChannel('pramana-session'); channel.postMessage('changed'); channel.close() } })
      }}>Sign out</button></div>{children}</div>
  return <SignIn onSignedIn={(value) => { setIdentity(value); setError('') }} initialError={error} onRetry={() => { startup = undefined; setChecking(true); setRetry((n) => n + 1) }} />
}

function AuthFrame({ children }: { children: ReactNode }) {
  useEffect(() => { window.scrollTo(0, 0) }, [])
  return <main className="auth-page">
    <header className="auth-brand"><a className="app-brand" href="#/draft-workspace"><span className="app-logo-mark" aria-hidden="true">P</span><strong>Pramana</strong></a><span className="auth-brand-note">A considered approach to brand governance.</span><a className="auth-about-link" href="#how-pramana-works" onClick={(event) => { event.preventDefault(); document.getElementById('how-pramana-works')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }) }}>Meet your review desk <Icon name="arrow" /></a></header>
    <div className="auth-layout">
      <section className="auth-story" aria-labelledby="auth-story-title"><p className="eyebrow"><span className="auth-kicker-line" />Before your next publish</p><h1 id="auth-story-title">Every word<br />carries <em>your brand.</em></h1><p className="auth-lead">Give it a thoughtful review. Pramana brings your draft, brand rules and source evidence together—so your team can make the final call with clarity.</p><div className="auth-story-note"><Icon name="shield" /><span>Evidence-led review.<br /><strong>Human judgment, always.</strong></span></div></section>
      <section className="access-card auth-card" aria-label="Account access">{children}</section>
      <section className="auth-product" id="how-pramana-works" aria-labelledby="auth-product-title"><div className="auth-product-top"><span className="eyebrow">Inside your review desk</span><span className="auth-specimen-label">An illustrated workflow</span></div><h2 id="auth-product-title">From first draft to a considered decision.</h2>
        <ol className="auth-process"><li><span className="auth-process-number">01</span><div><h3>Your draft</h3><p>Write, paste or import. Confirm extracted text before review.</p></div><Icon name="edit" /></li><li><span className="auth-process-number">02</span><div><h3>The evidence</h3><p>Inspect findings, quoted passages and versioned sources.</p></div><Icon name="file" /></li><li><span className="auth-process-number">03</span><div><h3>Your decision</h3><p>Review the exact draft and record an explicit human decision.</p></div><Icon name="check" /></li></ol>
        <div className="auth-product-bottom"><span className="auth-flow-dot" aria-hidden="true" />Your copy stays yours. Pramana never auto-publishes.</div>
      </section>
      <div className="auth-principles"><p><span>Clarity over guesswork</span>Check against configured brand rules.</p><p><span>Context behind each finding</span>Keep the source and draft version in view.</p><p><span>A record of your review</span>Retain evidence and human decisions.</p></div>
    </div><footer className="auth-footer"><span>Pramana · Pre-publication brand review</span><span>Evidence informs. Humans decide.</span></footer>
  </main>
}

function SignIn({ onSignedIn, initialError, onRetry }: { onSignedIn: (value: SessionIdentity | null) => void; initialError: string; onRetry: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      if (mode === 'reset') { await resetPassword(email.trim()); setNotice('If an eligible account exists, a password reset link will arrive shortly. Check your inbox and spam folder.') }
      else if (mode === 'signup') { await emailSignUp(email.trim(), password); setNotice('Check your inbox to verify your email, then return here to sign in.'); setMode('login') }
      else onSignedIn(await emailSignIn(email.trim(), password))
    } catch (err) { setError(signInError(err, mode === 'signup')) }
    finally { setPassword(''); setBusy(false) }
  }
  async function social(provider: 'google' | 'github', redirect = false) {
    setBusy(true); setError(''); setNotice('')
    try { const result = await socialSignIn(provider, redirect); if (result) onSignedIn(result) }
    catch (err) { setError(signInError(err)) }
    finally { setBusy(false) }
  }
  function switchMode(value: typeof mode) { setMode(value); setError(''); setNotice(''); setPassword('') }
  return <AuthFrame>
    <header className="access-heading"><p className="eyebrow">Your editorial workspace</p><h2>{mode === 'signup' ? 'Make room for better copy.' : mode === 'reset' ? 'A fresh start.' : 'Welcome to your desk.'}</h2><p className="muted-copy">{mode === 'signup' ? 'Create an account to begin your review.' : mode === 'reset' ? 'Request a secure link to reset your password.' : 'Sign in to begin a thoughtful review.'}</p></header>
    {mode !== 'reset' && <><div className="auth-social"><button className="secondary-button" disabled={busy} onClick={() => { void social('google') }}><ProviderMark provider="google" />Continue with Google</button><button className="secondary-button" disabled={busy} onClick={() => { void social('github') }}><ProviderMark provider="github" />Continue with GitHub</button></div>
      <details className="auth-redirect"><summary>Prefer to sign in in this window?</summary><div className="decision-actions"><button className="text-button" disabled={busy} onClick={() => { void social('google', true) }}>Google redirect</button><button className="text-button" disabled={busy} onClick={() => { void social('github', true) }}>GitHub redirect</button></div></details><div className="auth-divider"><span>or use your email</span></div></>}
    <form onSubmit={(event) => { void submit(event) }} aria-busy={busy}>
      <label className="field-label" htmlFor="auth-email">Email address<input id="auth-email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} value={email} maxLength={254} onChange={(event) => setEmail(event.target.value)} required disabled={busy} /></label>
      {mode !== 'reset' && <label className="field-label" htmlFor="auth-password">Password<input id="auth-password" type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} value={password} maxLength={4096} onChange={(event) => setPassword(event.target.value)} required disabled={busy} />{mode === 'signup' && <span className="muted-copy">Use a unique password. Your provider’s password policy applies.</span>}</label>}
      {mode === 'login' && <button type="button" className="text-button auth-forgot" disabled={busy} onClick={() => switchMode('reset')}>Forgot password?</button>}
      <button className="primary-button" disabled={busy}>{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}<Icon name="arrow" /></button>
    </form>
    {(error || initialError) && <div className="error-box auth-feedback" role="alert"><p className="error-message">{error || initialError}</p>{initialError && <button className="text-button" disabled={busy} onClick={onRetry}>Retry session check</button>}</div>}
    {notice && <p className="demo-notice auth-feedback" role="status">{notice}</p>}
    <div className="auth-switch">{mode === 'login' ? <>New here? <button className="text-button" disabled={busy} onClick={() => switchMode('signup')}>Create an account</button></> : <button className="text-button" disabled={busy} onClick={() => switchMode('login')}>Back to sign in</button>}</div>
    <p className="muted-copy access-footnote">New accounts start in a private personal workspace. Organization membership is assigned by an administrator. Use the same sign-in method each time; account linking is not available here.</p>
  </AuthFrame>
}

function ProviderMark({ provider }: { provider: 'google' | 'github' }) {
  return provider === 'google' ? <svg className="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285f4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.36Z"/><path fill="#34a853" d="M12 22c2.7 0 4.96-.9 6.62-2.42l-3.24-2.51c-.9.6-2.04.97-3.38.97-2.6 0-4.81-1.76-5.6-4.13H3.05v2.59A10 10 0 0 0 12 22Z"/><path fill="#fbbc05" d="M6.4 13.91A6 6 0 0 1 6.09 12c0-.66.11-1.31.31-1.91V7.5H3.05A10 10 0 0 0 2 12c0 1.61.38 3.14 1.05 4.5l3.35-2.59Z"/><path fill="#ea4335" d="M12 5.96c1.47 0 2.79.51 3.83 1.51l2.87-2.87A9.62 9.62 0 0 0 12 2a10 10 0 0 0-8.95 5.5l3.35 2.59C7.19 7.72 9.4 5.96 12 5.96Z"/></svg>
    : <svg className="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .75a11.25 11.25 0 0 0-3.56 21.92c.56.1.77-.24.77-.54v-2.1c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.73 1.16 1.73 1.16 1 1.72 2.64 1.22 3.28.93.1-.73.39-1.22.71-1.5-2.5-.29-5.13-1.25-5.13-5.56 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.98 0 0 .95-.31 3.1 1.16A10.8 10.8 0 0 1 12 6.16c.96 0 1.92.13 2.82.38 2.15-1.47 3.1-1.16 3.1-1.16.61 1.55.23 2.7.11 2.98.72.79 1.16 1.8 1.16 3.03 0 4.32-2.63 5.27-5.14 5.55.4.35.76 1.03.76 2.08v3.1c0 .3.2.65.78.54A11.25 11.25 0 0 0 12 .75Z"/></svg>
}
