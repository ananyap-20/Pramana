interface NavItem {
  path: string
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { path: 'draft-workspace', label: 'Draft workspace' },
  { path: 'review-and-sign-off', label: 'Human review' },
  { path: 'evidence-receipts', label: 'Evidence receipts' },
  { path: 'audit-trail-and-history', label: 'Review history' },
  { path: 'brand-guidelines-and-rules', label: 'Brand rules' },
]

interface SidebarProps {
  activePath: string
  onNavigate: (path: string) => void
}

export function Sidebar({ activePath, onNavigate }: SidebarProps) {
  return (
    <aside className="app-sidebar" aria-label="Main navigation">
      <a className="app-brand" href="#/draft-workspace" onClick={(event) => { event.preventDefault(); onNavigate('draft-workspace') }}>
        <span className="app-logo-mark" aria-hidden="true">P</span>
        <span>
          <strong>Pramana</strong>
          <small>Brand governance demo</small>
        </span>
      </a>

      <nav className="app-nav">
        {NAV_ITEMS.map((item) => {
          const isActive = activePath === item.path
          return (
            <a
              key={item.path}
              className={`app-nav-item${isActive ? ' is-active' : ''}`}
              href={`#/${item.path}`}
              aria-current={isActive ? 'page' : undefined}
              onClick={(event) => { event.preventDefault(); onNavigate(item.path) }}
            >
              {item.label}
            </a>
          )
        })}
      </nav>

      <div className="app-sidebar-footer">
        <strong>LumaDesk</strong>
        <span>Fictional brand · demo rules v1</span>
      </div>
    </aside>
  )
}
