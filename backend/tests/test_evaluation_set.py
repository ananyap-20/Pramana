"""Synthetic Day 2 evaluation cases; results are test assertions, not performance claims."""

import pytest

from app.domain import FindingCategory
from app.services.rule_engine import evaluate_draft
from app.services.seed_data import build_lumadesk_configuration


@pytest.mark.parametrize(
    ("name", "draft", "expected_categories"),
    [
        (
            "discouraged_term",
            "Open the dashboard to review project work.",
            [FindingCategory.TERMINOLOGY],
        ),
        (
            "prohibited_claim",
            "This update is guaranteed to eliminate all errors.",
            [FindingCategory.PROHIBITED_PHRASE],
        ),
        (
            "conflicting_fact",
            "Starter plan supports 50 team members.",
            [
                FindingCategory.CONFLICTING_FACT,
                FindingCategory.REQUIRED_DISCLAIMER,
            ],
        ),
        (
            "missing_disclaimer",
            "Feature availability changes between plans.",
            [FindingCategory.REQUIRED_DISCLAIMER],
        ),
        (
            "clean_draft",
            "Our workspace helps teams coordinate project conversations.",
            [],
        ),
        (
            "ambiguous_unsupported_claim",
            "Our workspace is the most loved solution for every team.",
            [],
        ),
        (
            "false_positive_boundary",
            "The dashboarding workshop starts at 50 seats.",
            [],
        ),
    ],
)
def test_day2_evaluation_set(
    name: str, draft: str, expected_categories: list[FindingCategory]
) -> None:
    findings = evaluate_draft(draft, build_lumadesk_configuration())

    assert [finding.category for finding in findings] == expected_categories, name

