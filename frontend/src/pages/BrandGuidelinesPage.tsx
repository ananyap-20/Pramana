import { CATEGORY_LABELS } from '../reviewLabels'
import { useEffect, useState } from 'react'
import { ApiError, getDemoConfig, type DemoConfigResponse, type FindingCategory } from '../api/client'
import { Icon } from '../components/Icon'

export function BrandGuidelinesPage() {
  const [config, setConfig] = useState<DemoConfigResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getDemoConfig('lumadesk', controller.signal).then((value) => { if (!controller.signal.aborted) setConfig(value) })
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(err instanceof ApiError ? err.detail : 'Could not load active policies. Check your API connection.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [attempt])

  return <div className="page-stack">
    <header className="page-heading page-heading-row"><div><p className="eyebrow">Governance registry · fictional demo brand</p><h1>Active policy repository</h1><p>The rules behind every review. Inspect their purpose and pinned source versions before evaluating a draft.</p></div>
      <a className="primary-button" href="#/draft-workspace"><Icon name="edit" />Open Draft Studio</a></header>
    {loading && <p className="loading-copy" role="status">Loading active brand policies…</p>}
    {error && <div className="error-box" role="alert"><p className="error-message">{error}</p><button className="secondary-button" onClick={() => { setError(''); setLoading(true); setAttempt((n) => n + 1) }}>Retry policies</button></div>}
    {config && !loading && <><div className="review-summary"><div><span className="summary-label">Brand</span><strong className="summary-value">{config.brand_name}</strong></div><div><span className="summary-label">Active rules</span><strong className="summary-value">{config.rules.length}</strong></div><div><span className="summary-label">Evaluation</span><strong>Deterministic checks</strong></div><div><span className="summary-label">Final approval</span><strong>Human reviewer</strong></div></div>
      {config.rules.length ? <div className="policy-grid">{config.rules.map((rule, index) => <article className="policy-card" key={rule.rule_id}>
        <div className="section-topline"><span className="policy-number">POLICY {String(index + 1).padStart(2, '0')}</span><span className="category-badge">Active · {rule.version}</span></div>
        <h2>{CATEGORY_LABELS[rule.category as FindingCategory] ?? rule.category.replaceAll('_', ' ')}</h2><p>{rule.description}</p>
        <details><summary>Rule & source versions</summary><dl className="provenance-rows"><dt>Rule</dt><dd><code>{rule.rule_id} @ {rule.version}</code></dd><dt>Source</dt><dd><code>{rule.source_id} @ {rule.source_version}</code></dd></dl></details>
        <footer><span className="muted-copy">Evaluated on submitted copy</span><a href="#/draft-workspace">Review a draft →</a></footer>
      </article>)}</div> : <section className="empty-state"><h2>No active rules</h2><p>The backend returned an empty rule set. Ask your administrator to configure brand policies.</p></section>}
    </>}
    <section className="review-panel"><h2>Evidence before conclusions.</h2><p className="muted-copy">This screen shows the current configuration. Saved review receipts keep the rule and source versions used at evaluation time. A matching citation alone does not establish that a finding is correct.</p><p className="muted-copy">Policy editing, custom rule creation and channel filters are unavailable in the current API. The reference’s warranty, logistics and FTC examples are not this backend’s configured rules.</p></section>
  </div>
}
