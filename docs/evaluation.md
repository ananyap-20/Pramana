# Synthetic evaluator regression set

The seeded LumaDesk configuration and all examples below are fictional. The automated cases verify known behavior for four narrow rules; they do not estimate accuracy on real brand content.

| Case | Input or condition | Expected behavior | Automated evidence |
|---|---|---|---|
| Discouraged terminology | `dashboard` | One terminology finding with exact phrase and approved source | `test_day2_evaluation_set[discouraged_term]` |
| Prohibited phrase | `guaranteed to eliminate all errors` | One prohibited-phrase finding | `test_day2_evaluation_set[prohibited_claim]` |
| Conflicting plan fact | Starter plan supports 50 team members | Contradicted fact finding; plan claim also triggers disclaimer finding | `test_day2_evaluation_set[conflicting_fact]` |
| Missing disclaimer | `Feature availability changes between plans.` | Required disclaimer finding | `test_day2_evaluation_set[missing_disclaimer]` |
| Plural disclaimer trigger | `Features and plans vary across tiers.` | Required disclaimer finding | `test_required_disclaimer_trigger_matches_plural_feature_and_plan_words` |
| Disclaimer already present | Required disclaimer is in the draft | No false missing-disclaimer finding | `test_required_disclaimer_is_not_missing_when_exact_text_exists` |
| Clean draft | No seeded trigger | No findings | `test_day2_evaluation_set[clean_draft]` |
| Ambiguous unsupported claim | “Most loved solution for every team” | No general fact finding; outside this demo's rules | `test_day2_evaluation_set[ambiguous_unsupported_claim]` |
| False-positive boundary | `dashboarding` or unrelated number 50 | No finding | `test_day2_evaluation_set[false_positive_boundary]` |
| Missing disclaimer already present | Draft includes the exact approved line | Validator rejects a false missing-disclaimer candidate | `test_missing_disclaimer_candidate_is_rejected_when_text_is_present` |
| Fabricated evidence | Candidate quote/source/rule does not match active input | Candidate is rejected before response | `test_finding_validator.py` |

## Limits

- The fact check recognizes only the seeded Starter plan maximum of 10 team members and the specific conflicting 50-member claim.
- The prohibited-phrase check recognizes only the configured phrase.
- Terminology is limited to the seeded `dashboard` rule.
- The disclaimer check is triggered by narrow plan, feature, or availability language. It checks whether the exact approved disclaimer is already present.
- The system does not verify arbitrary claims, extract tables or images, run OCR, or decide whether a citation proves the underlying claim.
- A passing synthetic regression suite is not precision, recall, or real-world brand-compliance accuracy.

Full run evidence and integration checks are in [`test-matrix.md`](test-matrix.md).
