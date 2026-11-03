import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, auditRequest, getAuditToken, setAuditToken, type AuditIdentity } from '../api/client'

export function AuditAccess() {
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [identity, setIdentity] = useState<AuditIdentity | null>(null)
  const connected = !!getAuditToken()

  useEffect(() => {
    if (!connected) return
    let cancelled = false
    auditRequest<AuditIdentity>('/me').then((value) => { if (!cancelled) setIdentity(value) })
      .catch(() => { if (!cancelled) setError('Your audit access could not be verified. Reconnect or contact your administrator.') })
    return () => { cancelled = true }
  }, [connected])

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setAuditToken(token.trim())
      await auditRequest<AuditIdentity>('/me')
      window.location.reload()
    } catch (err) {
      setAuditToken('')
      setError(err instanceof ApiError ? err.detail : 'Could not connect. Check the server and access key.')
    } finally { setBusy(false) }
  }

  return <section className="audit-access" aria-label="Audit access">
    {connected ? <>
      <span>{identity ? `${identity.actor_id} · ${identity.organization_id} · ${identity.role} · ${identity.retention_days}-day retention` : 'Verifying audit access…'}</span>
      <button className="secondary-button" onClick={() => { setAuditToken(''); window.location.reload() }}>Disconnect</button>
    </> : <form onSubmit={(event) => { void connect(event) }}>
      <label htmlFor="audit-key">Connect your organization access key for saved reviews and analytics</label>
      <input id="audit-key" type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" minLength={32} maxLength={256} required />
      <button className="secondary-button" disabled={busy}>{busy ? 'Connecting…' : 'Connect'}</button>
      <span className="muted-copy">Use the key issued by your administrator. It stays in this browser tab.</span>
    </form>}
    {error && <p className="error-message" role="alert">{error}</p>}
  </section>
}
