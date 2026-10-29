import { type ReactNode, useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { AuditTrailPage } from './pages/AuditTrailPage'
import { BrandGuidelinesPage } from './pages/BrandGuidelinesPage'
import { DraftWorkspacePage } from './pages/DraftWorkspacePage'
import { EvidenceReceiptsPage } from './pages/EvidenceReceiptsPage'
import { HumanReviewPage } from './pages/HumanReviewPage'

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
    default:
      content = <DraftWorkspacePage />
  }

  return (
    <Shell activePath={page} onNavigate={navigate}>
      {content}
    </Shell>
  )
}
