"""Domain types shared by the deterministic engine and validator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FindingCategory(StrEnum):
    TERMINOLOGY = "terminology"
    PROHIBITED_PHRASE = "prohibited_phrase"
    CONFLICTING_FACT = "conflicting_fact"
    REQUIRED_DISCLAIMER = "required_disclaimer"


class EvidenceStatus(StrEnum):
    SUPPORTED = "Supported"
    CONTRADICTED = "Contradicted"
    UNSUPPORTED = "Unsupported (needs verification)"
    INDETERMINATE = "Indeterminate (needs verification)"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REVISION = "revision"
    REJECTED = "rejected"


@dataclass(frozen=True)
class SourceVersion:
    source_id: str
    version: str
    title: str
    content: str
    approved: bool = True


@dataclass(frozen=True)
class RuleVersion:
    rule_id: str
    version: str
    category: FindingCategory
    description: str
    suggested_action: str
    source_id: str
    source_version: str
    source_excerpt: str
    active: bool = True


@dataclass(frozen=True)
class BrandConfiguration:
    brand_id: str
    brand_name: str
    rules: tuple[RuleVersion, ...]
    sources: tuple[SourceVersion, ...]

    def rule(self, rule_id: str, version: str) -> RuleVersion | None:
        return next(
            (rule for rule in self.rules if rule.rule_id == rule_id and rule.version == version),
            None,
        )

    def source(self, source_id: str, version: str) -> SourceVersion | None:
        return next(
            (
                source
                for source in self.sources
                if source.source_id == source_id and source.version == version
            ),
            None,
        )


@dataclass(frozen=True)
class DraftVersion:
    draft_id: str
    version: str
    text: str


@dataclass(frozen=True)
class TextLocation:
    start: int
    end: int


@dataclass(frozen=True)
class CandidateFinding:
    category: FindingCategory
    rule_id: str
    rule_version: str
    source_id: str
    source_version: str
    source_excerpt: str
    explanation: str
    suggested_action: str
    evidence_status: EvidenceStatus
    flagged_text: str | None = None
    location: TextLocation | None = None


@dataclass(frozen=True)
class ReviewRun:
    review_run_id: str
    brand_id: str
    draft: DraftVersion
    evaluated_at: datetime


@dataclass(frozen=True)
class ReviewDecisionRecord:
    decision_id: str
    decision: ReviewDecision
    decided_at: datetime


@dataclass(frozen=True)
class ReviewRecord:
    """History metadata retained without the submitted draft or receipt text."""

    review_run_id: str
    brand_id: str
    draft_id: str
    draft_version: str
    evaluated_at: datetime
    finding_count: int
    decisions: tuple[ReviewDecisionRecord, ...] = ()

    @property
    def current_decision(self) -> ReviewDecisionRecord | None:
        return self.decisions[-1] if self.decisions else None


@dataclass(frozen=True)
class EvidenceReceipt:
    finding_id: str
    review_run_id: str
    timestamp: datetime
    draft_id: str
    draft_version: str
    category: FindingCategory
    flagged_text: str | None
    location: TextLocation | None
    rule_id: str
    rule_version: str
    source_id: str
    source_version: str
    source_excerpt: str
    explanation: str
    evidence_status: EvidenceStatus
    suggested_action: str
    validation_outcome: str

