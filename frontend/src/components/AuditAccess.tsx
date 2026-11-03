import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, auditRequest, getAuditToken, setAuditToken, type AuditIdentity } from '../api/client'
import { Icon } from './Icon'

export function AuditAccess() {
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [identity, setIdentity] = useState<AuditIdentity | null>(null)
  const connected = !!getAuditToken()
  useEffect(() => {
    if (!connected) return
    const controller = new AbortController()
    auditRequest<AuditIdentity>('/me', { signal: controller.signal }).then((value) => { if (!controller.signal.aborted) setIdentity(value) })
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(err instanceof ApiError ? `Access could not be verified: ${err.detail}` : 'Could not connect to the audit service. Retry or contact your administrator.') })
    return () => controller.abort()
  }, [connected])
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setAuditToken(token.trim())
      await auditRequest<AuditIdentity>('/me')
      setToken('')
      window.location.hash = '#/draft-workspace'
      window.location.reload()
    } catch (err) {
      try { setAuditToken('') } catch { /* Storage failures are reported below. */ }
      setError(err instanceof ApiError ? `API error ${err.status}: ${err.detail}` : 'Could not connect. Check the API and allow session storage in this browser.')
    } finally { setBusy(false) }
  }
  return <div className="access-wrap"><section className="access-card" aria-labelledby="access-title">
    <header className="access-heading"><span className="category-badge"><Icon name="shield" />Organization audit access</span><h1 id="access-title">{connected ? 'Your reviewer account' : 'Reviewer sign in'}</h1><p className="muted-copy">An accountable review process.<br />Saved evidence, versioned drafts, human decisions.</p></header>
    {connected ? <>
      {!identity && !error && <p role="status">Verifying your access…</p>}
      {identity && <dl className="provenance-rows"><dt>Reviewer</dt><dd>{identity.actor_id}</dd><dt>Organization</dt><dd>{identity.organization_id}</dd><dt>Role</dt><dd>{identity.role}</dd><dt>Retention</dt><dd>{identity.retention_days} days</dd></dl>}
      <div className="decision-actions access-footnote"><a className="primary-button" href="#/draft-workspace">Enter Draft Studio<Icon name="arrow" /></a><button className="secondary-button" onClick={() => { setAuditToken(''); window.location.reload() }}>Disconnect</button></div>
    </> : <form onSubmit={(event) => { void connect(event) }}>
      <label className="field-label" htmlFor="audit-key">Organization access key<input id="audit-key" type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} minLength={32} maxLength={256} required disabled={busy} aria-describedby="key-help" /></label>
      <p className="muted-copy" id="key-help">Use the key issued by your administrator. It stays in this browser tab’s session storage and is sent only to the configured Pramana API. Connecting clears the active review from this tab.</p>
      <button className="primary-button" disabled={busy}>{busy ? 'Verifying access…' : 'Authenticate & enter studio'}<Icon name="arrow" /></button>
      <a className="secondary-button" href="#/draft-workspace">Continue in fictional demo mode</a>
    </form>}
    {error && <div className="error-box" role="alert"><p className="error-message">{error}</p>{connected && <button className="secondary-button" onClick={() => window.location.reload()}>Retry verification</button>}</div>}
    <div className="access-footnote"><p className="muted-copy"><strong>Need access?</strong> Contact your organization administrator. Self-service sign-up, password recovery, SSO and hardware-key sign-in are not implemented.</p><p className="muted-copy">Audit mode retains encrypted completed reviews for the configured period. It does not promise zero retention or a compliance certificate.</p></div>
  </section></div>
}
