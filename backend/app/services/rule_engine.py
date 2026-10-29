"""Pure, deterministic LumaDesk rule checks."""

from __future__ import annotations

import re

from app.domain import (
    BrandConfiguration,
    CandidateFinding,
    EvidenceStatus,
    FindingCategory,
    RuleVersion,
    TextLocation,
)
from app.services.seed_data import LUMADESK_DISCLAIMER


def _active_rule_for(
    configuration: BrandConfiguration, category: FindingCategory
) -> RuleVersion | None:
    """Return the first active rule for the given category, or None."""
    return next(
        (item for item in configuration.rules if item.category == category and item.active),
        None,
    )


def _candidate_from_match(
    *,
    draft_text: str,
    match: re.Match[str],
    rule: RuleVersion,
    evidence_status: EvidenceStatus,
) -> CandidateFinding:
    return CandidateFinding(
        category=rule.category,
        rule_id=rule.rule_id,
        rule_version=rule.version,
        source_id=rule.source_id,
        source_version=rule.source_version,
        source_excerpt=rule.source_excerpt,
        explanation=rule.description,
        suggested_action=rule.suggested_action,
        evidence_status=evidence_status,
        flagged_text=draft_text[match.start() : match.end()],
        location=TextLocation(start=match.start(), end=match.end()),
    )


def terminology_findings(draft_text: str, configuration: BrandConfiguration) -> list[CandidateFinding]:
    rule = _active_rule_for(configuration, FindingCategory.TERMINOLOGY)
    if rule is None:
        return []
    pattern = re.compile(r"(?<!\w)dashboard(?!\w)", re.IGNORECASE)
    return [
        _candidate_from_match(
            draft_text=draft_text,
            match=match,
            rule=rule,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        for match in pattern.finditer(draft_text)
    ]


def prohibited_phrase_findings(
    draft_text: str, configuration: BrandConfiguration
) -> list[CandidateFinding]:
    rule = _active_rule_for(configuration, FindingCategory.PROHIBITED_PHRASE)
    if rule is None:
        return []
    pattern = re.compile(
        r"(?<!\w)guaranteed\s+to\s+eliminate\s+all\s+errors(?!\w)", re.IGNORECASE
    )
    return [
        _candidate_from_match(
            draft_text=draft_text,
            match=match,
            rule=rule,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        for match in pattern.finditer(draft_text)
    ]


def conflicting_fact_findings(
    draft_text: str, configuration: BrandConfiguration
) -> list[CandidateFinding]:
    rule = _active_rule_for(configuration, FindingCategory.CONFLICTING_FACT)
    if rule is None:
        return []
    pattern = re.compile(
        r"(?<!\w)starter\s+plan\s+supports\s+50\s+team\s+members(?!\w)",
        re.IGNORECASE,
    )
    return [
        _candidate_from_match(
            draft_text=draft_text,
            match=match,
            rule=rule,
            evidence_status=EvidenceStatus.CONTRADICTED,
        )
        for match in pattern.finditer(draft_text)
    ]


def missing_disclaimer_findings(
    draft_text: str, configuration: BrandConfiguration
) -> list[CandidateFinding]:
    rule = _active_rule_for(configuration, FindingCategory.REQUIRED_DISCLAIMER)
    if rule is None:
        return []
    if LUMADESK_DISCLAIMER.casefold() in draft_text.casefold():
        return []
    trigger = re.compile(r"(?<!\w)(?:plans?|features?|availability)(?!\w)", re.IGNORECASE)
    if not trigger.search(draft_text):
        return []

    return [
        CandidateFinding(
            category=rule.category,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            source_id=rule.source_id,
            source_version=rule.source_version,
            source_excerpt=rule.source_excerpt,
            explanation=rule.description,
            suggested_action=rule.suggested_action,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
    ]


def evaluate_draft(draft_text: str, configuration: BrandConfiguration) -> list[CandidateFinding]:
    """Evaluate all four deterministic checks without performing validation."""

    return [
        *terminology_findings(draft_text, configuration),
        *prohibited_phrase_findings(draft_text, configuration),
        *conflicting_fact_findings(draft_text, configuration),
        *missing_disclaimer_findings(draft_text, configuration),
    ]


