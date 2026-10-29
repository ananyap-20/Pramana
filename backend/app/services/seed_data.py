"""Stable fictional LumaDesk configuration shared by API and tests."""

from __future__ import annotations

from app.domain import BrandConfiguration, FindingCategory, RuleVersion, SourceVersion


LUMADESK_BRAND_ID = "lumadesk"
LUMADESK_DISCLAIMER = "Features and availability may vary by plan."


def build_lumadesk_configuration() -> BrandConfiguration:
    """Return immutable fictional approved rules and evidence at version v1."""

    sources = (
        SourceVersion(
            source_id="lumadesk-brand-language",
            version="v1",
            title="LumaDesk Brand Language Guide (fictional)",
            content="Use workspace when describing the LumaDesk product area. Avoid dashboard.",
        ),
        SourceVersion(
            source_id="lumadesk-claims-policy",
            version="v1",
            title="LumaDesk Claims Policy (fictional)",
            content="Do not claim: guaranteed to eliminate all errors.",
        ),
        SourceVersion(
            source_id="lumadesk-plan-facts",
            version="v1",
            title="LumaDesk Plan Facts (fictional)",
            content="Starter plan supports max 10 team members.",
        ),
        SourceVersion(
            source_id="lumadesk-disclaimer-policy",
            version="v1",
            title="LumaDesk Disclaimer Policy (fictional)",
            content=LUMADESK_DISCLAIMER,
        ),
    )
    rules = (
        RuleVersion(
            rule_id="preferred-terminology-workspace",
            version="v1",
            category=FindingCategory.TERMINOLOGY,
            description="Prefer workspace; discourage dashboard.",
            suggested_action="Replace dashboard with workspace.",
            source_id="lumadesk-brand-language",
            source_version="v1",
            source_excerpt="Use workspace when describing the LumaDesk product area. Avoid dashboard.",
        ),
        RuleVersion(
            rule_id="prohibited-guaranteed-no-errors",
            version="v1",
            category=FindingCategory.PROHIBITED_PHRASE,
            description="The phrase guaranteed to eliminate all errors is prohibited.",
            suggested_action="Remove the prohibited guarantee and use an approved, supportable claim.",
            source_id="lumadesk-claims-policy",
            source_version="v1",
            source_excerpt="Do not claim: guaranteed to eliminate all errors.",
        ),
        RuleVersion(
            rule_id="starter-plan-team-limit",
            version="v1",
            category=FindingCategory.CONFLICTING_FACT,
            description="Starter plan supports max 10 team members, not 50.",
            suggested_action="Replace the 50-member statement with the approved 10-member limit.",
            source_id="lumadesk-plan-facts",
            source_version="v1",
            source_excerpt="Starter plan supports max 10 team members.",
        ),
        RuleVersion(
            rule_id="plan-feature-availability-disclaimer",
            version="v1",
            category=FindingCategory.REQUIRED_DISCLAIMER,
            description="Plan, feature, and availability claims require the approved disclaimer.",
            suggested_action=f"Add this disclaimer exactly: {LUMADESK_DISCLAIMER}",
            source_id="lumadesk-disclaimer-policy",
            source_version="v1",
            source_excerpt=LUMADESK_DISCLAIMER,
        ),
    )
    return BrandConfiguration(
        brand_id=LUMADESK_BRAND_ID,
        brand_name="LumaDesk (fictional demo brand)",
        rules=rules,
        sources=sources,
    )

