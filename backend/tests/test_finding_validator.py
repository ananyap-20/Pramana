from dataclasses import replace
from datetime import UTC, datetime

from app.domain import DraftVersion, EvidenceStatus, ReviewRun
from app.services.finding_validator import validate_candidate
from app.services.rule_engine import evaluate_draft
from app.services.seed_data import build_lumadesk_configuration


def _run(draft_text: str) -> ReviewRun:
    return ReviewRun(
        review_run_id="run-1",
        brand_id="lumadesk",
        draft=DraftVersion(draft_id="draft-1", version="v1", text=draft_text),
        evaluated_at=datetime.now(UTC),
    )


def _candidate_and_run():
    draft = "Our dashboard is ready."
    return evaluate_draft(draft, build_lumadesk_configuration())[0], _run(draft)


def test_valid_candidate_becomes_validated_receipt() -> None:
    candidate, run = _candidate_and_run()
    result = validate_candidate(candidate, build_lumadesk_configuration(), run)

    assert result.is_valid
    assert result.receipt is not None
    assert result.receipt.validation_outcome == "validated"


def test_fabricated_draft_quote_is_rejected() -> None:
    candidate, run = _candidate_and_run()
    invalid = replace(candidate, flagged_text="invented quote")

    result = validate_candidate(invalid, build_lumadesk_configuration(), run)
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "invalid_draft_quote"


def test_fabricated_excerpt_is_rejected() -> None:
    candidate, run = _candidate_and_run()
    invalid = replace(candidate, source_excerpt="fabricated source excerpt")

    result = validate_candidate(invalid, build_lumadesk_configuration(), run)
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "rule_source_mismatch"


def test_nonexistent_source_is_rejected() -> None:
    candidate, run = _candidate_and_run()
    invalid = replace(candidate, source_id="not-an-approved-source")

    result = validate_candidate(invalid, build_lumadesk_configuration(), run)
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "rule_source_mismatch"


def test_mismatched_rule_version_is_rejected() -> None:
    candidate, run = _candidate_and_run()
    invalid = replace(candidate, rule_version="v999")

    result = validate_candidate(invalid, build_lumadesk_configuration(), run)
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "invalid_rule_reference"


def test_unsupported_status_is_never_coerced_to_contradicted() -> None:
    candidate, run = _candidate_and_run()
    result = validate_candidate(
        replace(candidate, evidence_status=EvidenceStatus.UNSUPPORTED),
        build_lumadesk_configuration(),
        run,
    )

    assert result.is_valid
    assert result.receipt is not None
    assert result.receipt.evidence_status == EvidenceStatus.UNSUPPORTED


def test_missing_content_candidate_is_valid_without_a_quote() -> None:
    draft = "This plan introduces a new feature."
    candidate = evaluate_draft(draft, build_lumadesk_configuration())[0]
    result = validate_candidate(candidate, build_lumadesk_configuration(), _run(draft))

    assert result.is_valid
    assert result.receipt is not None
    assert result.receipt.flagged_text is None


def test_non_disclaimer_candidate_requires_a_draft_quote() -> None:
    draft = "dashboard"
    candidate = evaluate_draft(draft, build_lumadesk_configuration())[0]
    invalid = replace(candidate, flagged_text=None, location=None)

    result = validate_candidate(invalid, build_lumadesk_configuration(), _run(draft))

    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "missing_draft_evidence"


def test_missing_disclaimer_candidate_is_rejected_when_text_is_present() -> None:
    configuration = build_lumadesk_configuration()
    candidate = evaluate_draft("Feature launch this quarter.", configuration)[0]
    draft_with_disclaimer = "Features launch this quarter. Features and availability may vary by plan."

    result = validate_candidate(
        candidate,
        configuration,
        _run(draft_with_disclaimer),
    )

    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "required_text_present"


def test_candidate_explanation_must_match_approved_rule() -> None:
    candidate, run = _candidate_and_run()
    invalid = replace(candidate, explanation="An invented explanation.")

    result = validate_candidate(invalid, build_lumadesk_configuration(), run)

    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "rule_content_mismatch"

