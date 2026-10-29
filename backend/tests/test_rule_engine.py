from app.domain import FindingCategory
from app.services.rule_engine import evaluate_draft
from app.services.seed_data import LUMADESK_DISCLAIMER, build_lumadesk_configuration


def test_all_four_deterministic_checks_find_one_issue_each() -> None:
    draft = (
        "Our dashboard is guaranteed to eliminate all errors. "
        "Starter plan supports 50 team members. Features launch this quarter."
    )
    findings = evaluate_draft(draft, build_lumadesk_configuration())

    assert [finding.category for finding in findings] == [
        FindingCategory.TERMINOLOGY,
        FindingCategory.PROHIBITED_PHRASE,
        FindingCategory.CONFLICTING_FACT,
        FindingCategory.REQUIRED_DISCLAIMER,
    ]
    assert findings[0].flagged_text == "dashboard"
    assert findings[3].flagged_text is None
    assert findings[3].location is None


def test_clean_draft_has_no_findings() -> None:
    draft = "Our workspace helps teams coordinate project conversations."
    assert evaluate_draft(draft, build_lumadesk_configuration()) == []


def test_term_and_phrase_matching_are_case_insensitive_but_boundary_safe() -> None:
    draft = "DASHBOARD dashboarding. GUARANTEED TO ELIMINATE ALL ERRORS; erroring."
    findings = evaluate_draft(draft, build_lumadesk_configuration())

    assert [finding.flagged_text for finding in findings] == [
        "DASHBOARD",
        "GUARANTEED TO ELIMINATE ALL ERRORS",
    ]


def test_conflicting_fact_does_not_apply_general_numeric_heuristics() -> None:
    draft = "Starter plan supports 10 team members. Our workspace has 50 templates."
    findings = evaluate_draft(draft, build_lumadesk_configuration())

    assert not [
        finding for finding in findings if finding.category == FindingCategory.CONFLICTING_FACT
    ]


def test_required_disclaimer_is_not_missing_when_exact_text_exists() -> None:
    draft = f"Our plan includes new features. {LUMADESK_DISCLAIMER}"
    findings = evaluate_draft(draft, build_lumadesk_configuration())

    assert not [
        finding for finding in findings if finding.category == FindingCategory.REQUIRED_DISCLAIMER
    ]


def test_required_disclaimer_trigger_matches_plural_feature_and_plan_words() -> None:
    findings = evaluate_draft(
        "Features and plans vary across tiers.",
        build_lumadesk_configuration(),
    )

    assert [finding.category for finding in findings] == [FindingCategory.REQUIRED_DISCLAIMER]


def test_multiple_matches_are_unique_per_rule_and_span() -> None:
    findings = evaluate_draft("dashboard and dashboard", build_lumadesk_configuration())
    locations = [finding.location for finding in findings]

    assert len(locations) == 2
    assert len({(location.start, location.end) for location in locations if location}) == 2

