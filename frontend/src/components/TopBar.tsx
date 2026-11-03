import { useEffect, useState } from 'react'
import { getHealth, getAuditToken } from '../api/client'
import { Icon } from './Icon'

export function TopBar() {
  const [state, setState] = useState<'checking' | 'connected' | 'unavailable'>('checking')
  const [storage, setStorage] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal).then((health) => {
      if (!controller.signal.aborted) { setState(health.status === 'ok' ? 'connected' : 'unavailable'); setStorage(health.persistence) }
    }).catch(() => { if (!controller.signal.aborted) setState('unavailable') })
    return () => controller.abort()
  }, [attempt])
  return <div className="connection-bar">
    <span className={`api-status is-${state}`} role="status"><span className="status-dot" />{state === 'checking' ? 'Checking API…' : state === 'connected' ? 'API connected' : 'API unavailable'}</span>
    {state === 'unavailable' && <button className="text-button" onClick={() => { setState('checking'); setAttempt((n) => n + 1) }}>Retry connection</button>}
    <span className="connection-detail">{getAuditToken() ? 'Organization access selected' : storage === 'in_memory_demo_not_durable' ? 'Shared demo · temporary history' : 'Fictional LumaDesk workspace'}</span>
    <a className="access-link" href="#/reviewer-access"><Icon name="user" />{getAuditToken() ? 'Reviewer account' : 'Connect reviewer access'}</a>
  </div>
}
