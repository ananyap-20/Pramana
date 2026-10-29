# Test matrix

Verified on 2026-10-29 against the locally prepared project copy. Backend run: **54 passed, 1 warning, 0 failures**. The warning is Starlette's deprecation notice for the httpx-based TestClient integration. Pass rate is 54/54 for this regression suite only; it is not real-world detection accuracy.

| ID | Scenario and input | Expected result | Actual result | Status / evidence |
|---|---|---|---|---|
| API-01 | Analyze mixed sample draft with all four seeded issues | Four validated receipts, exact draft returned, matching v1 rule/source | Four validated findings returned | PASS — `test_analyze_all_issues_returns_only_versioned_validated_receipts` |
| RULE-01 | Draft includes discouraged `dashboard` | Terminology receipt with exact quote and approved source | Expected single category | PASS — `test_day2_evaluation_set[discouraged_term]` |
| RULE-02 | Draft includes prohibited guarantee | Prohibited phrase receipt | Expected single category | PASS — `test_day2_evaluation_set[prohibited_claim]` |
| RULE-03 | Draft says Starter supports 50 members | Contradicted fact plus required-disclaimer receipt | Both expected categories | PASS — `test_day2_evaluation_set[conflicting_fact]` |
| RULE-04 | Draft says feature availability varies and omits disclaimer | Missing-disclaimer receipt | Finding returned; plural “Features” covered | PASS — disclaimer evaluator tests |
| RULE-05 | Draft already includes exact disclaimer | Do not report it missing | No false missing-disclaimer candidate | PASS — `test_required_disclaimer_is_not_missing_when_exact_text_exists` |
| RULE-06 | Clean or unsupported-superlative draft | No finding outside the configured rules | No findings | PASS — clean and ambiguous cases in `test_evaluation_set.py` |
| EVID-01 | Candidate includes invented quote/explanation/action | Reject candidate | Validator rejects mismatch | PASS — `test_finding_validator.py` |
| DOC-01 | Valid DOCX with three ordinary paragraphs | Extract text, run same checks, preserve paragraph count | 200 response, 3 paragraphs, 4 receipts | PASS — `test_docx_analysis_uses_the_same_validated_pipeline` |
| DOC-02 | `.txt`, malformed DOCX, empty DOCX, oversized upload/extraction | Safe 4xx response; no execution | Unsupported/malformed inputs rejected; size limit returns 413 | PASS — `test_api.py`, `test_document_intake.py` |
| REV-01 | Submit decision for an analyzed run and read history | Decision event and count appear; draft text absent from history | Revision event and four findings recorded | PASS — `test_review_decision_is_recorded_and_returned_in_history` |
| REV-02 | Change decision; send invalid decision or unknown run | Valid updates append; invalid gets 422; unknown gets 404 | Observed expected responses and event order | PASS — `test_review_decision_can_be_updated_and_invalid_or_unknown_requests_fail` |
| BUILD-01 | Python bytecode compilation | Complete without syntax errors | `python -m compileall -q backend` passed | PASS — local command |
| BUILD-02 | Frontend TypeScript production build | `tsc -b` and Vite finish successfully | Vite 8.3.5 build passed | PASS — `npm run build` |
| E2E-01 | Browser: submit demo -> inspect Evidence Receipts -> attest and request revision -> open history | Same run, exact draft, receipts and decision remain connected | Four receipts viewed; decision and run appeared in backend history | PASS — local browser/API run on 2026-10-29; analyze POST, decision POST, and history GET all returned 200 |
| UI-01 | Compact browser viewport (731 CSS px) | Navigation stays usable without horizontal page overflow | Responsive compact navigation observed | PASS — manual local browser inspection; 390 px viewport not separately inspected |

## Scope notes

- The browser check used the local demo and fictional sample content. It did not exercise a public deployment.
- The frontend API uses `VITE_API_BASE_URL`; production URL wiring is prepared but not connected to a deployed service.
- PDF/image/table/OCR behavior is not tested because those inputs are explicitly unsupported.
- No precision/recall or latency claim is supported by this dataset.
