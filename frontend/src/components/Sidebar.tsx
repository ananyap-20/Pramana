import { Icon, type IconName } from './Icon'

const NAV_ITEMS: { path: string; label: string; icon: IconName }[] = [
  { path: 'draft-workspace', label: 'Draft Studio', icon: 'edit' },
  { path: 'review-and-sign-off', label: 'Human Review', icon: 'check' },
  { path: 'evidence-receipts', label: 'Evidence', icon: 'file' },
  { path: 'audit-trail-and-history', label: 'Audit Trail', icon: 'history' },
  { path: 'brand-guidelines-and-rules', label: 'Active Policies', icon: 'shield' },
  { path: 'visual-checks', label: 'Visual Checks', icon: 'image' },
]

export function Sidebar({ activePath, onNavigate }: { activePath: string; onNavigate: (path: string) => void }) {
  return <nav className="app-nav" aria-label="Main navigation">
    {NAV_ITEMS.map((item) => <a key={item.path} className={`app-nav-item${activePath === item.path ? ' is-active' : ''}`}
      href={`#/${item.path}`} aria-current={activePath === item.path ? 'page' : undefined}
      onClick={(event) => { event.preventDefault(); onNavigate(item.path) }}>
      <Icon name={item.icon} /><span>{item.label}</span>
    </a>)}
  </nav>
}
