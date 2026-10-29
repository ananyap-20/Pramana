"""The evidence-integrity boundary for candidate findings."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.domain import (
    BrandConfiguration,
    CandidateFinding,
    EvidenceReceipt,
    FindingCategory,
    ReviewRun,
)


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    receipt: EvidenceReceipt | None = None
    error: ValidationError | None = None

    @property
    def is_valid(self) -> bool:
        return self.receipt is not None


def _invalid(code: str, message: str) -> ValidationResult:
    return ValidationResult(error=ValidationError(code=code, message=message))


def validate_candidate(
    candidate: CandidateFinding,
    configuration: BrandConfiguration,
    review_run: ReviewRun,
) -> ValidationResult:
    """Return a receipt only when all draft, rule, and source checks pass."""

    rule = configuration.rule(candidate.rule_id, candidate.rule_version)
    if rule is None or not rule.active:
        return _invalid("invalid_rule_reference", "Candidate does not reference an active approved rule version.")
    if rule.category != candidate.category:
        return _invalid("rule_category_mismatch", "Candidate category does not match the approved rule.")
    if (
        candidate.explanation != rule.description
        or candidate.suggested_action != rule.suggested_action
    ):
        return _invalid("rule_content_mismatch", "Candidate explanation does not match the approved rule.")
    if (
        rule.source_id != candidate.source_id
        or rule.source_version != candidate.source_version
        or rule.source_excerpt != candidate.source_excerpt
    ):
        return _invalid("rule_source_mismatch", "Candidate source evidence does not match its approved rule.")

    source = configuration.source(candidate.source_id, candidate.source_version)
    if source is None or not source.approved:
        return _invalid("invalid_source_reference", "Candidate does not reference an approved source version.")
    if candidate.source_excerpt not in source.content:
        return _invalid("invalid_source_excerpt", "Candidate excerpt is absent from the approved source version.")

    is_required_disclaimer = candidate.category == FindingCategory.REQUIRED_DISCLAIMER
    if is_required_disclaimer:
        if candidate.flagged_text is not None or candidate.location is not None:
            return _invalid(
                "unexpected_draft_quote",
                "A missing-disclaimer finding must describe an absent passage, not quote one.",
            )
        if candidate.source_excerpt.casefold() in review_run.draft.text.casefold():
            return _invalid(
                "required_text_present",
                "The required disclaimer is already present in the evaluated draft.",
            )
    else:
        if candidate.flagged_text is None or candidate.location is None:
            return _invalid(
                "missing_draft_evidence",
                "This finding category requires an exact quoted passage and location.",
            )
        start, end = candidate.location.start, candidate.location.end
        if start < 0 or end < start or end > len(review_run.draft.text):
            return _invalid("invalid_draft_location", "Candidate location is outside the evaluated draft version.")
        if review_run.draft.text[start:end] != candidate.flagged_text:
            return _invalid("invalid_draft_quote", "Candidate quote does not exist at the stated location.")

    return ValidationResult(
        receipt=EvidenceReceipt(
            finding_id=str(uuid4()),
            review_run_id=review_run.review_run_id,
            timestamp=review_run.evaluated_at,
            draft_id=review_run.draft.draft_id,
            draft_version=review_run.draft.version,
            category=candidate.category,
            flagged_text=candidate.flagged_text,
            location=candidate.location,
            rule_id=candidate.rule_id,
            rule_version=candidate.rule_version,
            source_id=candidate.source_id,
            source_version=candidate.source_version,
            source_excerpt=candidate.source_excerpt,
            explanation=candidate.explanation,
            evidence_status=candidate.evidence_status,
            suggested_action=candidate.suggested_action,
            validation_outcome="validated",
        )
    )

