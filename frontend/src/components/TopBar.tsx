import { useEffect, useState } from 'react'
import { getHealth, currentIdentity } from '../api/client'
import { Icon } from './Icon'

export function TopBar() {
  const [state, setState] = useState<'checking' | 'connected' | 'unavailable'>('checking')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal).then((health) => {
      if (!controller.signal.aborted) setState(health.status === 'ok' ? 'connected' : 'unavailable')
    }).catch(() => { if (!controller.signal.aborted) setState('unavailable') })
    return () => controller.abort()
  }, [attempt])
  return <div className="connection-bar">
    <span className={`api-status is-${state}`} role="status"><span className="status-dot" />{state === 'checking' ? 'Checking API…' : state === 'connected' ? 'API connected' : 'API unavailable'}</span>
    {state === 'unavailable' && <button className="text-button" onClick={() => { setState('checking'); setAttempt((n) => n + 1) }}>Retry connection</button>}
    <span className="connection-detail">{currentIdentity()?.workspace === 'organization' ? 'Organization workspace' : 'Personal workspace'} · authenticated access</span>
    <a className="access-link" href="#/reviewer-access"><Icon name="user" />Reviewer account</a>
  </div>
}
