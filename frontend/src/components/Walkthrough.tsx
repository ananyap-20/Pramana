import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'pramana.walkthrough.v2'
const steps = [
  { target: '[href="#/draft-workspace"].app-nav-item', route: 'draft-workspace', title: 'Your review starts in Draft Studio', text: 'This is where you write, import and check a draft. This short tour shows you where everything lives.' },
  { target: '[data-tour="draft-actions"]', route: 'draft-workspace', title: 'Paste copy or import a file', text: 'In Draft Studio, paste your draft or use Import file for DOCX, PDF or images. PDF and image text must be checked against its page previews and confirmed before analysis.' },
  { target: '[data-tour="analysis-results"]', fallback: '[data-tour="analyze"]', route: 'draft-workspace', title: 'Review one finding at a time', text: 'Analyze draft runs the configured checks. Expand a finding to read the exact quote and suggested action. Your draft stays under your control.' },
  { target: '[href="#/evidence-receipts"].app-nav-item', route: 'evidence-receipts', title: 'Inspect the evidence', text: 'Evidence shows the evaluated draft passage, source excerpt and versions. Unsupported (needs verification) means a claim needs checking; it does not mean false.' },
  { target: '[href="#/review-and-sign-off"].app-nav-item', route: 'review-and-sign-off', title: 'You make the final decision', text: 'Human Review brings the submitted draft and findings together. After reviewing them, record approval, request revision or reject. Your decision never publishes content.' },
  { target: '[href="#/audit-trail-and-history"].app-nav-item', route: 'audit-trail-and-history', title: 'Return to saved reviews', text: 'Audit Trail holds your workspace’s saved reviews and decisions. Active Policies shows the rules being checked. You can replay this tour from Walkthrough at any time.' },
]

export function Walkthrough({ activePath }: { activePath: string }) {
  const [step, setStep] = useState<number | null>(() => {
    try { return window.localStorage.getItem(STORAGE_KEY) ? null : 0 } catch { return 0 }
  })
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [placement, setPlacement] = useState<{ top: number; left: number } | null>(null)
  const [animatePosition, setAnimatePosition] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const positioned = useRef(false)
  const active = step !== null

  useEffect(() => {
    const start = () => { returnFocus.current = document.activeElement as HTMLElement; setStep(0) }
    window.addEventListener('pramana:start-tour', start)
    return () => window.removeEventListener('pramana:start-tour', start)
  }, [])

  useEffect(() => {
    if (!active) return
    const element = dialog.current
    returnFocus.current ??= document.activeElement as HTMLElement
    element?.showModal()
    return () => {
      element?.close()
      const target = returnFocus.current
      const destination = target && target !== document.body && target.isConnected ? target : document.getElementById('main-content')
      destination?.focus()
    }
  }, [active])

  useEffect(() => {
    if (step === null) return
    const current = steps[step]
    if (current.route && activePath !== current.route) {
      window.location.hash = `#/${current.route}`
      return
    }
    const target = document.querySelector(current.target) ?? (current.fallback ? document.querySelector(current.fallback) : null)
    target?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })
    const measure = () => {
      const targetRect = target?.getBoundingClientRect() ?? null
      setRect(targetRect)
      const box = dialog.current?.getBoundingClientRect()
      if (!targetRect || !box) { setPlacement(null); return }
      const gap = 12
      const margin = 16
      const below = window.innerHeight - targetRect.bottom - margin
      const above = targetRect.top - margin
      const placeBelow = below >= box.height + gap || below >= above
      const top = placeBelow ? targetRect.bottom + gap : targetRect.top - box.height - gap
      const left = targetRect.left + targetRect.width / 2 - box.width / 2
      setPlacement({
        top: Math.max(margin, Math.min(top, window.innerHeight - box.height - margin)),
        left: Math.max(margin, Math.min(left, window.innerWidth - box.width - margin)),
      })
      if (positioned.current) setAnimatePosition(true)
      positioned.current = true
    }
    measure()
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => { window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true) }
  }, [step, activePath])

  function finish() {
    try { window.localStorage.setItem(STORAGE_KEY, 'seen') } catch { /* Tour remains usable without storage. */ }
    setStep(null)
    setRect(null)
    setPlacement(null)
    setAnimatePosition(false)
    positioned.current = false
  }

  const placementStyle = placement ? { top: placement.top, left: placement.left, right: 'auto', bottom: 'auto' } : undefined
  return <dialog ref={dialog} className={`tour-dialog${animatePosition ? ' tour-dialog-animated' : ''}`} style={placementStyle} aria-labelledby="tour-title" aria-describedby="tour-copy"
    onCancel={(event) => { event.preventDefault(); finish() }}>
    {step !== null && <>
      {rect && <div className="tour-spotlight" aria-hidden="true" style={{ top: Math.max(0, rect.top - 5), left: Math.max(0, rect.left - 5), width: rect.width + 10, height: rect.height + 10 }} />}
      <p className="eyebrow">Welcome to Pramana · {step + 1} / {steps.length}</p>
      <h2 id="tour-title">{steps[step].title}</h2><p id="tour-copy">{steps[step].text}</p>
      <div className="decision-actions">
        <button className="text-button tour-skip" onClick={finish}>Skip tour</button>
        <button className="secondary-button" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button className="primary-button" onClick={() => step === steps.length - 1 ? finish() : setStep(step + 1)}>{step === steps.length - 1 ? 'Get started' : 'Next'}</button>
      </div>
    </>}
  </dialog>
}
