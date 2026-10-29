import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

interface ShellProps {
  activePath: string
  children: ReactNode
  onNavigate: (path: string) => void
}

export function Shell({ activePath, children, onNavigate }: ShellProps) {
  return (
    <div className="app-shell">
      <Sidebar activePath={activePath} onNavigate={onNavigate} />
      <div className="app-main">
        <TopBar />
        <main className="app-page-main">
          <div className="app-content">{children}</div>
        </main>
      </div>
    </div>
  )
}
