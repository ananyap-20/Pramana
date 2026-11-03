"""Stable contracts for organization-scoped review history and analytics."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.intake_models import ImmutableModel
from app.schemas import AnalyzeResponse, ReviewDecisionLiteral


class AuditProblem(ValueError):
    """Safe audit failure translated to HTTP only at the API boundary."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class AuditError(ImmutableModel):
    detail: str


class AuditDecisionRequest(ImmutableModel):
    decision: ReviewDecisionLiteral
    expected_revision: int = Field(ge=0, le=100)


class AuditAnalyzeRequest(ImmutableModel):
    brand_id: str = Field(min_length=1, max_length=100)
    draft_text: str = Field(min_length=1, max_length=100000)


class AuditEvent(ImmutableModel):
    decision_id: str
    decision: ReviewDecisionLiteral
    decided_at: datetime
    actor_id: str
    revision: int
    request_id: str


class AuditRun(ImmutableModel):
    review_run_id: str
    brand_id: str
    draft_id: str
    draft_version: str
    draft_sha256: str
    configuration_sha256: str
    engine_version: str
    evaluated_at: datetime
    expires_at: datetime
    actor_id: str
    request_id: str
    input_type: str
    finding_count: int
    revision: int
    current_decision: ReviewDecisionLiteral | None
    current_decision_at: datetime | None
    decision_history: tuple[AuditEvent, ...]


class AuditHistory(ImmutableModel):
    records: tuple[AuditRun, ...]
    next_cursor: str | None


class AuditSnapshot(ImmutableModel):
    analysis: AnalyzeResponse
    configuration: dict


class AuditAnalytics(ImmutableModel):
    schema_version: Literal["1.0"] = "1.0"
    brand_id: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    timezone: Literal["UTC"] = "UTC"
    total_runs: int
    total_findings: int
    decision_events: int
    outcomes: dict[str, int]
    categories: dict[str, int]
    repeated_rules: tuple[dict, ...]
    daily: tuple[dict, ...]
    definition: str
