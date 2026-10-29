import { useEffect, useState } from 'react'
import { getDemoConfig, type DemoConfigResponse, type DemoRuleResponse, ApiError } from '../api/client'

const DEMO_BRAND_ID = 'lumadesk'

const CATEGORY_META: Record<string, { icon: string; color: string; bg: string }> = {
  terminology: { icon: 'spellcheck', color: '#004967', bg: 'rgba(151, 215, 255, 0.3)' },
  prohibited_phrase: { icon: 'block', color: '#93000a', bg: '#ffdad6' },
  conflicting_fact: { icon: 'warning', color: '#705d00', bg: '#f7e7bd' },
  required_disclaimer: { icon: 'gavel', color: '#004967', bg: 'rgba(202, 230, 255, 0.25)' },
}

function categoryLabel(cat: string): string {
  return cat
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function BrandGuidelinesPage() {
  const [config, setConfig] = useState<DemoConfigResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedRule, setExpandedRule] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getDemoConfig(DEMO_BRAND_ID)
      .then((data) => {
        if (!cancelled) setConfig(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load brand configuration')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const categoryCounts = config
    ? config.rules.reduce<Record<string, number>>((acc, r) => {
        acc[r.category] = (acc[r.category] || 0) + 1
        return acc
      }, {})
    : {}

  return (
    <div>
      {/* Page header */}
      <div style={{ marginBottom: '2rem' }}>
        <h1
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '32px',
            fontWeight: 700,
            color: '#004967',
            margin: 0,
            lineHeight: '40px',
          }}
        >
          Brand guidelines & rules
        </h1>
        <p
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '15px',
            color: '#40484e',
            marginTop: '0.5rem',
            lineHeight: '22px',
          }}
        >
          Active governance rules loaded from the brand configuration. Every draft submitted for
          review is checked against these rules.
        </p>
      </div>

      {/* Loading state */}
      {loading && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '30vh',
            gap: '0.75rem',
          }}
        >
          <span
            className="material-symbols-outlined"
            style={{
              fontSize: '28px',
              color: '#19648f',
              animation: 'spin 1s linear infinite',
            }}
          >
            progress_activity
          </span>
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: '15px', color: '#40484e' }}>
            Loading brand configuration…
          </span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          style={{
            padding: '1.5rem',
            borderRadius: '0.75rem',
            backgroundColor: '#ffdad6',
            border: '1px solid #ba1a1a',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '24px', color: '#93000a' }}>
            error
          </span>
          <div>
            <p
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: '15px',
                fontWeight: 600,
                color: '#93000a',
                margin: 0,
              }}
            >
              Failed to load configuration
            </p>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#93000a', margin: '4px 0 0 0' }}>
              {error}
            </p>
          </div>
        </div>
      )}

      {/* Loaded state */}
      {config && !loading && (
        <>
          {/* Brand info card */}
          <div
            style={{
              padding: '1.5rem',
              borderRadius: '0.75rem',
              backgroundColor: '#ffffff',
              border: '1px solid rgba(77, 141, 186, 0.18)',
              boxShadow: '0 1px 3px rgba(10, 42, 58, 0.04)',
              marginBottom: '1.5rem',
              display: 'flex',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div
                  style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '0.5rem',
                    backgroundColor: '#004967',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ color: '#fff', fontSize: '22px' }}
                  >
                    verified
                  </span>
                </div>
                <div>
                  <h2
                    style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: '22px',
                      fontWeight: 600,
                      color: '#004967',
                      margin: 0,
                    }}
                  >
                    {config.brand_name}
                  </h2>
                  <span
                    style={{
                      fontFamily: 'monospace',
                      fontSize: '12px',
                      color: '#40484e',
                    }}
                  >
                    brand_id: {config.brand_id}
                  </span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              {/* Total rules chip */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  backgroundColor: 'rgba(202, 230, 255, 0.25)',
                  border: '1px solid rgba(77, 141, 186, 0.2)',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '28px',
                    fontWeight: 700,
                    color: '#004967',
                    lineHeight: 1,
                  }}
                >
                  {config.rules.length}
                </span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', color: '#40484e' }}>
                  Active Rules
                </span>
              </div>

              {/* Category breakdown chips */}
              {Object.entries(categoryCounts).map(([cat, count]) => {
                const meta = CATEGORY_META[cat] ?? { icon: 'rule', color: '#40484e', bg: '#f1e2b7' }
                return (
                  <div
                    key={cat}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px',
                      borderRadius: '9999px',
                      backgroundColor: meta.bg,
                      fontFamily: 'var(--font-sans)',
                      fontSize: '13px',
                      fontWeight: 500,
                      color: meta.color,
                    }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                      {meta.icon}
                    </span>
                    {count} {categoryLabel(cat)}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Rules grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(22rem, 1fr))',
              gap: '1rem',
            }}
          >
            {config.rules.map((rule) => (
              <RuleCard
                key={rule.rule_id}
                rule={rule}
                isExpanded={expandedRule === rule.rule_id}
                onToggle={() =>
                  setExpandedRule((prev) => (prev === rule.rule_id ? null : rule.rule_id))
                }
              />
            ))}
          </div>
        </>
      )}

      {/* Spin animation */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

function RuleCard({
  rule,
  isExpanded,
  onToggle,
}: {
  rule: DemoRuleResponse
  isExpanded: boolean
  onToggle: () => void
}) {
  const meta = CATEGORY_META[rule.category] ?? { icon: 'rule', color: '#40484e', bg: '#f1e2b7' }

  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid rgba(77, 141, 186, 0.18)',
        borderRadius: '0.75rem',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        boxShadow: '0 1px 3px rgba(10, 42, 58, 0.04)',
        transition: 'box-shadow 0.2s, transform 0.15s',
        cursor: 'pointer',
      }}
      onClick={onToggle}
      onMouseEnter={(e) => {
        const el = e.currentTarget
        el.style.boxShadow = '0 4px 12px rgba(10, 42, 58, 0.10)'
        el.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget
        el.style.boxShadow = '0 1px 3px rgba(10, 42, 58, 0.04)'
        el.style.transform = 'translateY(0)'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '2rem',
              height: '2rem',
              borderRadius: '0.375rem',
              backgroundColor: meta.bg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: '18px', color: meta.color }}
            >
              {meta.icon}
            </span>
          </div>
          <h3
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '16px',
              fontWeight: 600,
              color: '#004967',
              margin: 0,
              lineHeight: '22px',
            }}
          >
            {rule.rule_id.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          </h3>
        </div>

        {/* Version badge */}
        <span
          style={{
            fontFamily: 'monospace',
            fontSize: '11px',
            fontWeight: 500,
            color: '#40484e',
            padding: '2px 8px',
            borderRadius: '9999px',
            backgroundColor: '#f7e7bd',
            whiteSpace: 'nowrap',
          }}
        >
          v{rule.version}
        </span>
      </div>

      {/* Category pill */}
      <span
        style={{
          alignSelf: 'flex-start',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 10px',
          borderRadius: '9999px',
          backgroundColor: meta.bg,
          fontFamily: 'var(--font-sans)',
          fontSize: '12px',
          fontWeight: 500,
          color: meta.color,
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>
          {meta.icon}
        </span>
        {categoryLabel(rule.category)}
      </span>

      {/* Description */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '14px',
          lineHeight: '20px',
          color: '#40484e',
          margin: 0,
        }}
      >
        {rule.description}
      </p>

      {/* Expanded: source info */}
      {isExpanded && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '0.5rem',
            backgroundColor: '#fff8f0',
            border: '1px solid rgba(77, 141, 186, 0.15)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            marginTop: '4px',
          }}
        >
          <MetaRow label="Rule ID" value={rule.rule_id} mono />
          <MetaRow label="Version" value={rule.version} />
          <MetaRow label="Source ID" value={rule.source_id} mono />
          <MetaRow label="Source Version" value={rule.source_version} />
        </div>
      )}

      {/* Expand indicator */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#19648f',
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: '18px', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)' }}>
          expand_more
        </span>
      </div>
    </div>
  )
}

function MetaRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: '0.5rem' }}>
      <span
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '12px',
          fontWeight: 500,
          color: '#40484e',
          minWidth: '6.5rem',
          flexShrink: 0,
        }}
      >
        {label}:
      </span>
      <span
        style={{
          fontFamily: mono ? 'monospace' : 'var(--font-sans)',
          fontSize: '12px',
          color: '#221b02',
          wordBreak: 'break-all',
        }}
      >
        {value}
      </span>
    </div>
  )
}
