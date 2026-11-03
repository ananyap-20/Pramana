import type { AnalyzeResponse, LocationResponse } from '../api/client'

export function DocumentProvenance({ review }: { review: AnalyzeResponse }) {
  const source = review.document_provenance
  if (!source) return null
  return (
    <details className="reading-section intake-provenance" aria-label="Confirmed transcription provenance">
      <summary>Confirmed document transcription · {source.file_type.toUpperCase()} · version {source.version}</summary>
      <p className="muted-copy">{source.file_type.toUpperCase()} · Extraction version {source.version} · {source.human_edited ? 'Includes human corrections; edited passages have no original-file coordinates.' : 'Accepted extraction text.'}</p>
      <p className="muted-copy">Transcription confirmed {new Date(source.confirmed_at).toLocaleString()} by {source.actor_kind === 'authenticated_user' ? `authenticated reviewer ${source.actor}` : 'the original capability holder'}. Content approval is a separate human decision.</p>
      <details><summary>File, text and extraction details</summary>
        <p>Original SHA-256: <code>{source.file_sha256}</code></p>
        <p>Accepted text SHA-256: <code>{source.text_sha256}</code></p>
        <p>Temporary extraction replay expires {new Date(source.original_available_until).toLocaleString()} or on server restart. Optional organization original-file storage follows separate server retention. A digest cannot replay a deleted file.</p>
        <p>{Object.entries(source.tools).map(([name, value]) => `${name}: ${value}`).join(' · ')}</p>
      </details>
    </details>
  )
}

export function FindingPageContext({ review, location }: { review: AnalyzeResponse; location: LocationResponse }) {
  const pages = review.document_provenance?.pages.filter((page) => location.start < page.end && location.end > page.start)
  if (!pages?.length) return null
  return <p className="muted-copy">{pages.map((page) => `Page ${page.page}: ${page.method === 'human_edited' ? 'human-edited text; original coordinates removed' : page.method === 'ocr' ? 'human-confirmed OCR transcription' : 'human-confirmed PDF text'}`).join(' · ')}</p>
}
