"""Orchestration that deliberately keeps candidates behind the validator."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.domain import DraftVersion, EvidenceReceipt, ReviewRun
from app.repositories.demo_repository import BrandConfigurationRepository, ReviewRunRepository
from app.services.finding_validator import validate_candidate
from app.services.rule_engine import evaluate_draft

logger = logging.getLogger(__name__)


class UnknownBrandError(ValueError):
    """Raised without exposing implementation details for an unknown brand."""


def analyze_draft(
    *,
    draft_text: str,
    brand_id: str,
    configuration_repository: BrandConfigurationRepository,
    review_run_repository: ReviewRunRepository,
) -> tuple[ReviewRun, list[EvidenceReceipt]]:
    configuration = configuration_repository.get_brand(brand_id)
    if configuration is None:
        raise UnknownBrandError("No approved configuration exists for this brand.")

    review_run = ReviewRun(
        review_run_id=str(uuid4()),
        brand_id=brand_id,
        draft=DraftVersion(draft_id=str(uuid4()), version="v1", text=draft_text),
        evaluated_at=datetime.now(UTC),
    )

    receipts: list[EvidenceReceipt] = []
    rejected_count = 0
    for candidate in evaluate_draft(draft_text, configuration):
        result = validate_candidate(candidate, configuration, review_run)
        if not result.is_valid:
            # Engine-generated candidates should pass validation. Log rejected
            # candidates for debugging without leaking them to the user.
            rejected_count += 1
            logger.warning(
                "Candidate rejected by validator: rule=%s code=%s message=%s",
                candidate.rule_id,
                result.error.code if result.error else "unknown",
                result.error.message if result.error else "unknown",
            )
            continue
        if result.receipt is None:
            # Defensive guard: is_valid should guarantee a receipt exists.
            # A bare assert would be removed by python -O.
            logger.error("Validator returned is_valid=True but receipt is None")
            continue
        receipts.append(result.receipt)

    if rejected_count:
        logger.info(
            "Review run %s: %d candidate(s) rejected by validator",
            review_run.review_run_id,
            rejected_count,
        )

    # The demo history retains metadata and the validated finding count only.
    # The submitted draft and receipt passages remain in the response to the
    # submitting browser and are not kept in the process-local history store.
    review_run_repository.record_review_run(review_run, finding_count=len(receipts))

    return review_run, receipts

