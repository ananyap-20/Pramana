"""Explicitly non-durable repository for the fictional Day 1 demo."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.domain import (
    BrandConfiguration,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewRecord,
    ReviewRun,
)
from app.services.seed_data import build_lumadesk_configuration


MAX_REVIEW_RECORDS = 100


class UnknownReviewRunError(ValueError):
    """Raised when a decision refers to a run absent from the demo history."""


class BrandConfigurationRepository(Protocol):
    def get_brand(self, brand_id: str) -> BrandConfiguration | None: ...


class ReviewRunRepository(Protocol):
    def record_review_run(self, review_run: ReviewRun, finding_count: int) -> None: ...
    def get_review_record(self, review_run_id: str) -> ReviewRecord | None: ...
    def record_review_decision(
        self, review_run_id: str, decision: ReviewDecision, decided_at: datetime
    ) -> ReviewDecisionRecord: ...
    def list_review_runs(self, brand_id: str) -> list[ReviewRecord]: ...


class InMemoryDemoRepository:
    """A bounded, process-local demo store; it is deliberately not durable."""

    def __init__(self, max_review_records: int = MAX_REVIEW_RECORDS) -> None:
        configuration = build_lumadesk_configuration()
        self._brands = {configuration.brand_id: configuration}
        self._review_records: dict[str, ReviewRecord] = {}
        self._max_review_records = max(1, max_review_records)
        self._lock = RLock()

    def get_brand(self, brand_id: str) -> BrandConfiguration | None:
        with self._lock:
            return self._brands.get(brand_id)

    def record_review_run(self, review_run: ReviewRun, finding_count: int) -> None:
        """Store history metadata only; the draft and receipt text are not retained."""
        record = ReviewRecord(
            review_run_id=review_run.review_run_id,
            brand_id=review_run.brand_id,
            draft_id=review_run.draft.draft_id,
            draft_version=review_run.draft.version,
            evaluated_at=review_run.evaluated_at,
            finding_count=finding_count,
        )
        with self._lock:
            self._review_records[record.review_run_id] = record
            while len(self._review_records) > self._max_review_records:
                oldest_id = min(
                    self._review_records,
                    key=lambda run_id: self._review_records[run_id].evaluated_at,
                )
                del self._review_records[oldest_id]

    def get_review_record(self, review_run_id: str) -> ReviewRecord | None:
        with self._lock:
            return self._review_records.get(review_run_id)

    def record_review_decision(
        self, review_run_id: str, decision: ReviewDecision, decided_at: datetime
    ) -> ReviewDecisionRecord:
        with self._lock:
            record = self._review_records.get(review_run_id)
            if record is None:
                raise UnknownReviewRunError("Review run was not found in the current demo history.")

            decision_record = ReviewDecisionRecord(
                decision_id=str(uuid4()),
                decision=decision,
                decided_at=decided_at,
            )
            self._review_records[review_run_id] = replace(
                record, decisions=(*record.decisions, decision_record)
            )
            return decision_record

    def list_review_runs(self, brand_id: str) -> list[ReviewRecord]:
        """Return review runs for a brand, most recent first."""
        with self._lock:
            runs = [r for r in self._review_records.values() if r.brand_id == brand_id]
        runs.sort(key=lambda r: r.evaluated_at, reverse=True)
        return runs


