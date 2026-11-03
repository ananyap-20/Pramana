import { useEffect, useState, type ReactNode } from 'react'
import { getReadiness } from '../api/client'

export function WelcomeTransition({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<'loading' | 'fading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 12_000)
    let active = true
    getReadiness(controller.signal).then(() => {
      if (active) setPhase('fading')
    }).catch(() => { if (active) setPhase('error') })
      .finally(() => window.clearTimeout(timeout))
    return () => { active = false; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])
  useEffect(() => {
    if (phase !== 'fading') return
    const timer = window.setTimeout(() => setPhase('ready'),
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 220)
    return () => window.clearTimeout(timer)
  }, [phase])
  // Mounting Shell after the handoff focuses the real main content.
  if (phase === 'ready') return children
  return <main className={`welcome-layer${phase === 'fading' ? ' is-leaving' : ''}`} aria-labelledby="welcome-title">
    <img className="welcome-logo" src="/favicon.svg" alt="Pramana P brand mark" width="96" height="96" />
    <p className="eyebrow">Pramana</p>
    <h1 id="welcome-title">Welcome to your desk.</h1>
    <p>Give your words a thoughtful review. Evidence informs. Humans decide.</p>
    {phase === 'error' ? <div className="welcome-error" role="alert">
      <p>We couldn’t reach the review service. Check your connection and retry. A waking server may need a moment.</p>
      <button className="primary-button" onClick={() => { setPhase('loading'); setAttempt((n) => n + 1) }}>Retry</button>
    </div> : <p className="muted-copy" role="status">Preparing your review desk…</p>}
  </main>
}
