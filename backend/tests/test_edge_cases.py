"""Edge-case tests for rule engine and finding validator robustness."""

from dataclasses import replace
from datetime import UTC, datetime

from app.domain import (
    BrandConfiguration,
    DraftVersion,
    EvidenceStatus,
    FindingCategory,
    ReviewRun,
    RuleVersion,
    SourceVersion,
)
from app.services.finding_validator import validate_candidate
from app.services.rule_engine import evaluate_draft
from app.services.seed_data import build_lumadesk_configuration


def _run(draft_text: str) -> ReviewRun:
    return ReviewRun(
        review_run_id="run-edge",
        brand_id="lumadesk",
        draft=DraftVersion(draft_id="draft-edge", version="v1", text=draft_text),
        evaluated_at=datetime.now(UTC),
    )


# ─── Rule engine edge cases ────────────────────────────────────────────────


def test_whitespace_only_draft_produces_no_findings() -> None:
    assert evaluate_draft("   \n\t  ", build_lumadesk_configuration()) == []


def test_punctuation_adjacent_to_keyword_still_matches() -> None:
    draft = 'The "dashboard" is outdated.'
    findings = evaluate_draft(draft, build_lumadesk_configuration())
    assert len(findings) == 1
    assert findings[0].flagged_text == "dashboard"


def test_keyword_inside_word_does_not_match() -> None:
    """'dashboarding' should not trigger the terminology rule."""
    draft = "Our dashboarding tool is excellent."
    findings = evaluate_draft(draft, build_lumadesk_configuration())
    terminology = [f for f in findings if f.category == FindingCategory.TERMINOLOGY]
    assert terminology == []


def test_multiple_occurrences_produce_unique_locations() -> None:
    draft = "dashboard first, then dashboard second"
    findings = evaluate_draft(draft, build_lumadesk_configuration())
    terminology = [f for f in findings if f.category == FindingCategory.TERMINOLOGY]
    assert len(terminology) == 2
    locs = {(f.location.start, f.location.end) for f in terminology if f.location}
    assert len(locs) == 2  # unique locations


def test_missing_disclaimer_has_no_fabricated_quote() -> None:
    """The missing-disclaimer finding should have no flagged_text or location."""
    draft = "New feature available for all plans."
    findings = evaluate_draft(draft, build_lumadesk_configuration())
    disclaimer_findings = [
        f for f in findings if f.category == FindingCategory.REQUIRED_DISCLAIMER
    ]
    assert len(disclaimer_findings) == 1
    assert disclaimer_findings[0].flagged_text is None
    assert disclaimer_findings[0].location is None


def test_inactive_rule_is_skipped_by_engine() -> None:
    """If a rule is marked inactive, the rule engine should not use it."""
    config = build_lumadesk_configuration()
    # Deactivate the terminology rule
    modified_rules = tuple(
        replace(r, active=False) if r.category == FindingCategory.TERMINOLOGY else r
        for r in config.rules
    )
    modified_config = replace(config, rules=modified_rules)

    draft = "Our dashboard is great."
    findings = evaluate_draft(draft, modified_config)
    # There should be no terminology findings since the rule is inactive
    # The only finding should be a missing disclaimer (due to trigger word presence)
    categories = [f.category for f in findings]
    assert FindingCategory.TERMINOLOGY not in categories


# ─── Validator edge cases ───────────────────────────────────────────────────


def test_out_of_bounds_location_is_rejected() -> None:
    config = build_lumadesk_configuration()
    draft = "dashboard"
    candidates = evaluate_draft(draft, config)
    assert len(candidates) >= 1
    # Corrupt the location to be out of bounds
    bad = replace(candidates[0], location=replace(candidates[0].location, end=9999))
    result = validate_candidate(bad, config, _run(draft))
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "invalid_draft_location"


def test_negative_location_is_rejected() -> None:
    config = build_lumadesk_configuration()
    draft = "dashboard"
    candidates = evaluate_draft(draft, config)
    assert len(candidates) >= 1
    bad = replace(candidates[0], location=replace(candidates[0].location, start=-1))
    result = validate_candidate(bad, config, _run(draft))
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "invalid_draft_location"


def test_unapproved_source_is_rejected() -> None:
    config = build_lumadesk_configuration()
    # Add an unapproved source and reference it from a candidate
    unapproved = SourceVersion(
        source_id="lumadesk-brand-language",
        version="v1",
        title="Unapproved",
        content="Use workspace when describing the LumaDesk product area. Avoid dashboard.",
        approved=False,
    )
    modified_config = replace(config, sources=(unapproved,) + config.sources[1:])

    draft = "dashboard"
    candidates = evaluate_draft(draft, config)
    result = validate_candidate(candidates[0], modified_config, _run(draft))
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "invalid_source_reference"


def test_category_mismatch_is_rejected() -> None:
    config = build_lumadesk_configuration()
    draft = "dashboard"
    candidates = evaluate_draft(draft, config)
    # Change the category to something different from the rule
    bad = replace(candidates[0], category=FindingCategory.CONFLICTING_FACT)
    result = validate_candidate(bad, config, _run(draft))
    assert not result.is_valid
    assert result.error is not None
    assert result.error.code == "rule_category_mismatch"
