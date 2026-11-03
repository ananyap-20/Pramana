import { useEffect, useRef, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { Icon } from './Icon'
import { Walkthrough } from './Walkthrough'

export function Shell({ activePath, children, onNavigate }: { activePath: string; children: ReactNode; onNavigate: (path: string) => void }) {
  const main = useRef<HTMLElement>(null)
  useEffect(() => { main.current?.focus(); window.scrollTo(0, 0) }, [activePath])
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
    <header className="app-header">
      <div className="header-brand-row">
        <a className="app-brand" href="#/draft-workspace"><span className="app-logo-mark" aria-hidden="true">P</span><strong>Pramana</strong></a>
        <span className="brand-edition">GUARDIAN</span>
        <span className="header-caption">Pre-publication brand review</span>
        <button className="guide-link text-button" onClick={() => window.dispatchEvent(new Event('pramana:start-tour'))}><Icon name="help" />Walkthrough</button>
      </div>
      <Sidebar activePath={activePath} onNavigate={onNavigate} />
    </header>
    <TopBar />
    <main ref={main} id="main-content" className="app-content" tabIndex={-1}>{children}</main>
    <footer className="app-footer"><span><span className="status-dot" />LumaDesk · fictional demo brand</span><span>Evidence informs. Humans decide.</span><a href="#/brand-guidelines-and-rules">View active rules <Icon name="arrow" /></a></footer>
    <Walkthrough />
  </div>
}
