import { useState } from 'react'

const steps = [
  { title: 'Add your draft', text: 'In Draft Studio, paste your copy or choose Import file. For a PDF or image, select Extract text, compare each preview, correct the transcription and confirm it. PDF/image intake must be enabled on the server.', link: '#/draft-workspace', action: 'Open Draft Studio' },
  { title: 'Run the review', text: 'Select Analyze draft, or Analyse confirmed text after confirming a PDF/image transcription. Pramana checks the submitted text against the configured brand rules.', link: '#/draft-workspace', action: 'Go to Draft Studio' },
  { title: 'Inspect the evidence', text: 'Read the findings and their quoted draft passages and source excerpts. Unsupported (needs verification) means a claim needs checking; it does not mean it is false.', link: '#/evidence-receipts', action: 'Open Evidence' },
  { title: 'Make the final decision', text: 'In Human Review, inspect the draft and findings, attest that you reviewed them, and record your decision. Pramana does not publish or rewrite your copy.', link: '#/review-and-sign-off', action: 'Open Human Review' },
]

export function GuidePage() {
  const [step, setStep] = useState(0)
  const current = steps[step]
  return <div className="page-stack">
    <header className="page-heading"><p className="eyebrow">Pramana walkthrough</p><h1>Review, step by step.</h1><p>Follow the process from draft to a human decision.</p></header>
    <section className="review-panel walkthrough" aria-label="Review walkthrough">
      <p className="eyebrow" aria-live="polite">Step {step + 1} of {steps.length}</p>
      <h2>{current.title}</h2><p>{current.text}</p>
      <div className="decision-actions">
        <button className="secondary-button" disabled={step === 0} onClick={() => setStep(step - 1)}>Previous</button>
        {step < steps.length - 1 ? <button className="primary-button" onClick={() => setStep(step + 1)}>Next step</button> : <button className="primary-button" onClick={() => setStep(0)}>Start again</button>}
        <a className="secondary-button" href={current.link}>{current.action} →</a>
      </div>
    </section>
    <div className="demo-notice">Use fictional, non-sensitive files in the demo. Checks cover configured rules and do not provide general fact checking or certification.</div>
  </div>
}
