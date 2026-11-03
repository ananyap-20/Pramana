import { type ReactNode, useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { AuditTrailPage } from './pages/AuditTrailPage'
import { BrandGuidelinesPage } from './pages/BrandGuidelinesPage'
import { DraftWorkspacePage } from './pages/DraftWorkspacePage'
import { EvidenceReceiptsPage } from './pages/EvidenceReceiptsPage'
import { HumanReviewPage } from './pages/HumanReviewPage'
import { VisualChecksPage } from './pages/VisualChecksPage'
import { GuidePage } from './pages/GuidePage'
import { WelcomeTransition } from './components/WelcomeTransition'

function getPageFromHash(): string {
  const hash = window.location.hash.replace(/^#\/?/, '')
  return hash || 'draft-workspace'
}

export default function App() {
  const [page, setPage] = useState(getPageFromHash)

  useEffect(() => {
    function onHashChange() {
      setPage(getPageFromHash())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navigate = useCallback((path: string) => {
    window.location.hash = `#/${path}`
  }, [])

  let content: ReactNode
  switch (page) {
    case 'draft-workspace':
      content = <DraftWorkspacePage />
      break
    case 'review-and-sign-off':
      content = <HumanReviewPage />
      break
    case 'evidence-receipts':
      content = <EvidenceReceiptsPage />
      break
    case 'audit-trail-and-history':
      content = <AuditTrailPage />
      break
    case 'brand-guidelines-and-rules':
      content = <BrandGuidelinesPage />
      break
    case 'visual-checks':
      content = <VisualChecksPage />
      break
    case 'guide':
      content = <GuidePage />
      break
    default:
      content = <section className="empty-state"><h1>Page not found</h1><p>Choose a workspace from the navigation.</p><a className="primary-button" href="#/draft-workspace">Return to Draft Studio</a></section>
  }

  return (
    <WelcomeTransition><Shell activePath={page} onNavigate={navigate}>
      {content}
    </Shell></WelcomeTransition>
  )
}
