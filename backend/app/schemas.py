"""Public HTTP schemas; candidates and validator internals never appear here."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import EvidenceReceipt, ReviewDecisionRecord, ReviewRecord

# Typed literals matching domain enums for API contract safety.
CategoryLiteral = Literal[
    "terminology", "prohibited_phrase", "conflicting_fact", "required_disclaimer"
]
EvidenceStatusLiteral = Literal[
    "Supported", "Contradicted",
    "Unsupported (needs verification)", "Indeterminate (needs verification)",
]


class HealthResponse(BaseModel):
    status: str
    persistence: str


class DemoRuleResponse(BaseModel):
    rule_id: str
    version: str
    category: CategoryLiteral
    description: str
    source_id: str
    source_version: str


class DemoConfigResponse(BaseModel):
    brand_id: str
    brand_name: str
    rules: list[DemoRuleResponse]


class AnalyzeRequest(BaseModel):
    brand_id: str = Field(min_length=1, max_length=100)
    draft_text: str = Field(min_length=1, max_length=100_000)


class LocationResponse(BaseModel):
    start: int
    end: int


class EvidenceReceiptResponse(BaseModel):
    finding_id: str
    review_run_id: str
    timestamp: datetime
    draft_id: str
    draft_version: str
    category: CategoryLiteral
    flagged_text: str | None
    location: LocationResponse | None
    rule_id: str
    rule_version: str
    source_id: str
    source_version: str
    source_excerpt: str
    explanation: str
    evidence_status: EvidenceStatusLiteral
    suggested_action: str
    validation_outcome: str

    @classmethod
    def from_domain(cls, receipt: EvidenceReceipt) -> "EvidenceReceiptResponse":
        location = (
            LocationResponse(start=receipt.location.start, end=receipt.location.end)
            if receipt.location is not None
            else None
        )
        return cls(
            finding_id=receipt.finding_id,
            review_run_id=receipt.review_run_id,
            timestamp=receipt.timestamp,
            draft_id=receipt.draft_id,
            draft_version=receipt.draft_version,
            category=receipt.category.value,
            flagged_text=receipt.flagged_text,
            location=location,
            rule_id=receipt.rule_id,
            rule_version=receipt.rule_version,
            source_id=receipt.source_id,
            source_version=receipt.source_version,
            source_excerpt=receipt.source_excerpt,
            explanation=receipt.explanation,
            evidence_status=receipt.evidence_status.value,
            suggested_action=receipt.suggested_action,
            validation_outcome=receipt.validation_outcome,
        )


class AnalyzeResponse(BaseModel):
    review_run_id: str
    brand_id: str
    draft_id: str
    draft_version: str
    evaluated_at: datetime
    persistence: str
    input_type: str
    draft_text: str
    paragraph_count: int | None = None
    findings: list[EvidenceReceiptResponse]


ReviewDecisionLiteral = Literal["approved", "revision", "rejected"]


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecisionLiteral


class ReviewDecisionEventResponse(BaseModel):
    decision_id: str
    decision: ReviewDecisionLiteral
    decided_at: datetime

    @classmethod
    def from_domain(cls, decision: ReviewDecisionRecord) -> "ReviewDecisionEventResponse":
        return cls(
            decision_id=decision.decision_id,
            decision=decision.decision.value,
            decided_at=decision.decided_at,
        )


class ReviewDecisionResponse(ReviewDecisionEventResponse):
    review_run_id: str

    @classmethod
    def from_domain(
        cls, review_run_id: str, decision: ReviewDecisionRecord
    ) -> "ReviewDecisionResponse":
        return cls(
            review_run_id=review_run_id,
            decision_id=decision.decision_id,
            decision=decision.decision.value,
            decided_at=decision.decided_at,
        )


class ReviewRunSummary(BaseModel):
    review_run_id: str
    brand_id: str
    draft_id: str
    draft_version: str
    evaluated_at: datetime
    finding_count: int
    current_decision: ReviewDecisionLiteral | None
    current_decision_at: datetime | None
    decision_history: list[ReviewDecisionEventResponse]

    @classmethod
    def from_domain(cls, record: ReviewRecord) -> "ReviewRunSummary":
        current_decision = record.current_decision
        return cls(
            review_run_id=record.review_run_id,
            brand_id=record.brand_id,
            draft_id=record.draft_id,
            draft_version=record.draft_version,
            evaluated_at=record.evaluated_at,
            finding_count=record.finding_count,
            current_decision=current_decision.decision.value if current_decision else None,
            current_decision_at=current_decision.decided_at if current_decision else None,
            decision_history=[
                ReviewDecisionEventResponse.from_domain(decision)
                for decision in record.decisions
            ],
        )
