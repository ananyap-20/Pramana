import { useEffect, useState } from 'react'
import { getHealth } from '../api/client'

type ApiState = 'checking' | 'connected' | 'unavailable'

export function TopBar() {
  const [apiState, setApiState] = useState<ApiState>('checking')

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((health) => {
        if (!cancelled) setApiState(health.status === 'ok' ? 'connected' : 'unavailable')
      })
      .catch(() => {
        if (!cancelled) setApiState('unavailable')
      })
    return () => { cancelled = true }
  }, [])

  const statusText = {
    checking: 'Checking API…',
    connected: 'API connected · in-memory demo',
    unavailable: 'API unavailable',
  }[apiState]

  return (
    <header className="app-topbar">
      <span className="topbar-title">Pramana <span>·</span> LumaDesk demo</span>
      <span className={`api-status is-${apiState}`} aria-live="polite">{statusText}</span>
    </header>
  )
}
