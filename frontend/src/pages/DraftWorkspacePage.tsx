import { useRef, useState } from 'react'
import {
  analyzeDocument,
  analyzeDraft,
  ApiError,
  clearCurrentReview,
  saveCurrentReview,
  type AnalyzeResponse,
} from '../api/client'
import { FindingCard } from '../components/FindingCard'

const DEMO_BRAND_ID = 'lumadesk'

// Demo text that exercises all 4 rules
const DEMO_DRAFT = `Our new LumaDesk dashboard is guaranteed to eliminate all errors for your entire team. The starter plan supports 50 team members. Features and pricing vary by plan. Get started this quarter with our enterprise tier.`

type SubmitState = 'idle' | 'loading' | 'done' | 'error'

export function DraftWorkspacePage() {
  const [draftText, setDraftText] = useState(DEMO_DRAFT)
  const [brandId] = useState(DEMO_BRAND_ID)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [docxFile, setDocxFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const submittingRef = useRef(false)

  async function handleAnalyze() {
    if (submittingRef.current) return
    submittingRef.current = true
    clearCurrentReview()
    setSubmitState('loading')
    setErrorMsg('')
    setResult(null)
    try {
      let response: AnalyzeResponse
      if (docxFile) {
        response = await analyzeDocument(brandId, docxFile)
      } else {
        if (!draftText.trim()) {
          setErrorMsg('Please enter draft text before analysing.')
          setSubmitState('error')
          return
        }
        response = await analyzeDraft({ brand_id: brandId, draft_text: draftText })
      }
      saveCurrentReview(response)
      setResult(response)
      setDraftText(response.draft_text)
      setDocxFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setSubmitState('done')
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(`API error ${err.status}: ${err.detail}`)
      } else if (err instanceof Error) {
        setErrorMsg(`Network error: ${err.message}`)
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
      setSubmitState('error')
    } finally {
      submittingRef.current = false
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    if (file && !file.name.toLowerCase().endsWith('.docx')) {
      setErrorMsg('Only .docx files are accepted.')
      setDocxFile(null)
      setResult(null)
      clearCurrentReview()
      setSubmitState('error')
      return
    }
    if (file && file.size > 5 * 1024 * 1024) {
      setErrorMsg('The .docx file must be 5 MiB or smaller.')
      setDocxFile(null)
      setResult(null)
      clearCurrentReview()
      setSubmitState('error')
      return
    }
    setDocxFile(file)
    clearCurrentReview()
    setErrorMsg('')
    setResult(null)
    setSubmitState('idle')
  }

  const wordCount = draftText.trim() ? draftText.trim().split(/\s+/).length : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', paddingBottom: '4rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <nav style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 500, color: '#40484e', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>Drafts</span>
          <span className="material-symbols-outlined" style={{ fontSize: '14px', color: '#19648f' }}>chevron_right</span>
          <span>LumaDesk Demo</span>
          <span className="material-symbols-outlined" style={{ fontSize: '14px', color: '#19648f' }}>chevron_right</span>
          <span style={{ color: '#004967', fontWeight: 600 }}>Working draft</span>
        </nav>
        <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: '32px', fontWeight: 700, color: '#004967', margin: 0, letterSpacing: '-0.01em', lineHeight: '40px' }}>
          Draft workspace
        </h1>
        <p style={{ fontFamily: 'var(--font-sans)', fontSize: '18px', fontWeight: 500, color: '#40484e', margin: 0, maxWidth: '48rem' }}>
          Run four deterministic checks against the fictional LumaDesk rules and inspect the approved source behind each finding.
        </p>
      </div>

      <div className="demo-notice" role="note">
        Public, unauthenticated demo: use fictional, non-sensitive copy only. The current draft stays in this browser tab. Shared history contains run IDs, finding counts, and human decisions, and resets when the service restarts.
      </div>

      {/* Draft meta bar */}
      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid rgba(77, 141, 186, 0.18)',
          borderRadius: '0.75rem',
          padding: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(10, 42, 58, 0.04)',
        }}
      >
        <div>
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 500, color: '#19648f', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Brand
          </span>
          <div style={{ fontFamily: 'var(--font-sans)', fontSize: '22px', fontWeight: 600, color: '#004967', marginTop: '2px' }}>
            LumaDesk (fictional demo brand)
          </div>
          <div style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#19648f' }}>person_outline</span>
              Fictional demo brand
            </span>
            <span style={{ color: '#19648f' }}>·</span>
            <span>{wordCount} words</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              height: '2.5rem',
              padding: '0 1rem',
              borderRadius: '0.5rem',
              border: '1px solid rgba(77, 141, 186, 0.5)',
              backgroundColor: 'transparent',
              color: '#004967',
              fontFamily: 'var(--font-sans)',
              fontSize: '15px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: 'pointer',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px', color: '#19648f' }}>upload_file</span>
            {docxFile ? docxFile.name : 'Upload .docx'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          {docxFile && (
            <button
              onClick={() => { setDocxFile(null); setResult(null); clearCurrentReview(); setSubmitState('idle'); }}
              style={{
                height: '2.5rem',
                padding: '0 1rem',
                borderRadius: '0.5rem',
                border: '1px solid rgba(186, 26, 26, 0.4)',
                backgroundColor: 'transparent',
                color: '#93000a',
                fontFamily: 'var(--font-sans)',
                fontSize: '15px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Clear file
            </button>
          )}
          <button
            onClick={handleAnalyze}
            disabled={submitState === 'loading'}
            style={{
              height: '2.5rem',
              padding: '0 1.25rem',
              borderRadius: '0.5rem',
              border: 'none',
              backgroundColor: submitState === 'loading' ? '#40484e' : '#086288',
              color: '#fff',
              fontFamily: 'var(--font-sans)',
              fontSize: '15px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: submitState === 'loading' ? 'not-allowed' : 'pointer',
              opacity: submitState === 'loading' ? 0.7 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: '18px', animation: submitState === 'loading' ? 'spin 1s linear infinite' : 'none' }}
            >
              {submitState === 'loading' ? 'sync' : 'play_arrow'}
            </span>
            {submitState === 'loading' ? 'Analysing…' : 'Analyse draft'}
          </button>
        </div>
      </div>

      {/* Error */}
      {submitState === 'error' && (
        <div
          style={{
            padding: '1rem 1.5rem',
            borderRadius: '0.75rem',
            backgroundColor: '#ffdad6',
            border: '1px solid rgba(186, 26, 26, 0.4)',
            color: '#93000a',
            fontFamily: 'var(--font-sans)',
            fontSize: '15px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>error</span>
          {errorMsg}
        </div>
      )}

      {/* Two-column workspace */}
      <div className="workspace-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,7fr) minmax(0,5fr)', gap: '2rem', alignItems: 'start' }}>
        {/* Left: editor */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontFamily: 'var(--font-sans)', fontSize: '22px', fontWeight: 600, color: '#004967', margin: 0 }}>Document draft</h2>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e' }}>
              {docxFile ? `Uploading: ${docxFile.name}` : 'Plain text editor'}
            </span>
          </div>
          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1px solid rgba(77, 141, 186, 0.18)',
              borderRadius: '0.75rem',
              padding: '1.5rem',
              boxShadow: '0 1px 3px rgba(10, 42, 58, 0.04)',
            }}
          >
            {docxFile ? (
              <div
                style={{
                  padding: '3rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '1rem',
                  color: '#40484e',
                  textAlign: 'center',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '48px', color: '#19648f' }}>description</span>
                <div style={{ fontFamily: 'var(--font-sans)', fontSize: '18px', fontWeight: 600, color: '#004967' }}>{docxFile.name}</div>
                <div style={{ fontFamily: 'var(--font-sans)', fontSize: '15px', color: '#40484e' }}>
                  {(docxFile.size / 1024).toFixed(1)} KB — ready for analysis
                </div>
                <div style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e' }}>
                  Text will be extracted and evaluated when you click "Analyse draft".
                </div>
              </div>
            ) : (
              <>
                <textarea
                  value={draftText}
                  maxLength={100_000}
                  onChange={(e) => { setDraftText(e.target.value); setResult(null); clearCurrentReview(); setSubmitState('idle') }}
                  placeholder="Paste or type your draft here…"
                  rows={18}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    border: 'none',
                    outline: 'none',
                    resize: 'vertical',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '15px',
                    lineHeight: '22px',
                    color: '#221b02',
                    backgroundColor: 'transparent',
                  }}
                />
              </>
            )}
          </div>
        </section>

        {/* Right: findings */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontFamily: 'var(--font-sans)', fontSize: '22px', fontWeight: 600, color: '#004967', margin: 0 }}>
              Rule check results
            </h2>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e' }}>
              {result ? `${result.findings.length} finding${result.findings.length !== 1 ? 's' : ''}` : '—'}
            </span>
          </div>

          {/* Empty / loading / results */}
          {submitState === 'idle' && !result && (
            <EmptyFindingsPlaceholder />
          )}
          {submitState === 'loading' && (
            <LoadingFindingsPlaceholder />
          )}
          {submitState === 'done' && result && result.findings.length === 0 && (
            <CleanDraftPlaceholder />
          )}
          {submitState === 'done' && result && result.findings.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Run meta */}
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '0.5rem',
                  backgroundColor: '#f1e2b7',
                  border: '1px solid rgba(77, 141, 186, 0.2)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: '13px',
                  color: '#40484e',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                  justifyContent: 'space-between',
                }}
              >
                <span>
                  <strong style={{ color: '#004967' }}>{result.findings.length}</strong> findings from backend analysis
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#40484e' }}>
                  Run: {result.review_run_id.slice(0, 8)}…
                </span>
              </div>
              {result.findings.map((f) => (
                <FindingCard key={f.finding_id} finding={f} />
              ))}
            </div>
          )}
        </section>
      </div>

      {submitState === 'done' && result && (
        <button
          className="primary-button"
          type="button"
          onClick={() => { window.location.hash = '#/review-and-sign-off' }}
        >
          Continue to human review
        </button>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @media (max-width: 1024px) {
          .workspace-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}

function EmptyFindingsPlaceholder() {
  return (
    <div
      style={{
        padding: '3rem 2rem',
        borderRadius: '0.75rem',
        border: '1px dashed rgba(77, 141, 186, 0.35)',
        backgroundColor: '#fdfcfa',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        textAlign: 'center',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '40px', color: '#19648f' }}>
        policy
      </span>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '15px', color: '#40484e', margin: 0 }}>
        Click <strong>"Analyse draft"</strong> to run the brand-policy check.
      </p>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e', margin: 0 }}>
        Findings returned by the backend will appear here.
      </p>
    </div>
  )
}

function LoadingFindingsPlaceholder() {
  return (
    <div
      style={{
        padding: '3rem 2rem',
        borderRadius: '0.75rem',
        border: '1px solid rgba(77, 141, 186, 0.2)',
        backgroundColor: '#ffffff',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
      }}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: '40px', color: '#19648f', animation: 'spin 1s linear infinite' }}
      >
        sync
      </span>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '15px', color: '#40484e', margin: 0 }}>
        Running brand-policy analysis…
      </p>
    </div>
  )
}

function CleanDraftPlaceholder() {
  return (
    <div
      style={{
        padding: '3rem 2rem',
        borderRadius: '0.75rem',
        border: '1px solid rgba(77, 141, 186, 0.2)',
        backgroundColor: '#ffffff',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        textAlign: 'center',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '40px', color: '#004967' }}>
        check_circle
      </span>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '15px', fontWeight: 600, color: '#004967', margin: 0 }}>
        No findings from the four configured checks
      </p>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#40484e', margin: 0 }}>
        No matching issue was returned for these seeded checks. This does not assess other brand requirements or general compliance.
      </p>
    </div>
  )
}
