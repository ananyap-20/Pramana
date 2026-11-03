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



def test_wrong_state_and_empty_span_cannot_be_serialized():
    candidate, run = _candidate_and_run()
    from app.domain import TextLocation
    for invalid in (replace(candidate, evidence_status="Approved"),
                    replace(candidate, evidence_status=EvidenceStatus.CONTRADICTED),
                    replace(candidate, flagged_text="", location=TextLocation(4, 4))):
        assert not validate_candidate(invalid, build_lumadesk_configuration(), run).is_valid


def test_citation_match_does_not_validate_unrelated_draft_passage():
    candidate, _ = _candidate_and_run()
    from app.domain import TextLocation
    invalid = replace(candidate, flagged_text="ready", location=TextLocation(4, 9))
    result = validate_candidate(invalid, build_lumadesk_configuration(), _run("Our ready copy."))
    assert result.error.code == "rule_not_satisfied"


def test_source_approval_drift_and_brand_mismatch_are_rejected():
    candidate, run = _candidate_and_run()
    config = build_lumadesk_configuration()
    config = replace(config, sources=tuple(replace(source, approved=False) for source in config.sources))
    assert validate_candidate(candidate, config, run).error.code == "invalid_source_reference"
    assert validate_candidate(candidate, replace(config, brand_id="other"), run).error.code == "brand_mismatch"


def test_unicode_offsets_and_duplicate_locations_remain_exact(monkeypatch):
    from app.repositories.demo_repository import InMemoryDemoRepository
    from app.services.review_service import analyze_draft
    draft = "\U0001f642 dashboard and DASHBOARD"
    config = build_lumadesk_configuration()
    candidates = evaluate_draft(draft, config)
    monkeypatch.setattr("app.services.review_service.evaluate_draft", lambda *args: candidates + candidates)
    repository = InMemoryDemoRepository()
    run, receipts = analyze_draft(draft_text=draft, brand_id="lumadesk", configuration_repository=repository, review_run_repository=repository)
    assert run.draft.text == draft
    assert len(receipts) == 2
    assert receipts[0].location != receipts[1].location
    for receipt in receipts:
        assert draft[receipt.location.start:receipt.location.end] == receipt.flagged_text


def test_orchestration_does_not_trust_citation_only_candidates(monkeypatch):
    from app.domain import TextLocation
    from app.repositories.demo_repository import InMemoryDemoRepository
    from app.services.review_service import analyze_draft
    candidate, _ = _candidate_and_run()
    forged = replace(candidate, flagged_text="ready", location=TextLocation(4, 9))
    monkeypatch.setattr("app.services.review_service.evaluate_draft", lambda *args: [forged])
    repository = InMemoryDemoRepository()
    _, receipts = analyze_draft(draft_text="Our ready copy.", brand_id="lumadesk", configuration_repository=repository, review_run_repository=repository)
    assert receipts == []
