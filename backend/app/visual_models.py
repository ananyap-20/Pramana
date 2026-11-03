"""Versioned, bounded static visual-check contract. No client-supplied approvals."""

from typing import Literal

from pydantic import Field, model_validator

from app.domain import EvidenceStatus
from app.intake_models import ImmutableModel


Selector = str  # Validated against the restricted selector grammar by the manifest loader.


class VisualAsset(ImmutableModel):
    asset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    media_type: Literal["image/png", "image/jpeg"]
    content_base64: str = Field(min_length=4, max_length=262144)


class VisualRequest(ImmutableModel):
    brand_id: str = Field(min_length=1, max_length=100)
    draft_id: str = Field(min_length=1, max_length=100)
    draft_version: str = Field(min_length=1, max_length=100)
    html: str = Field(min_length=1, max_length=100000)
    css: str = Field(default="", max_length=32000)
    assets: tuple[VisualAsset, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def unique_assets(self):
        if len({a.asset_id for a in self.assets}) != len(self.assets):
            raise ValueError("Asset IDs must be unique.")
        return self


class VisualError(ImmutableModel):
    detail: str


class PaletteTarget(ImmutableModel):
    selector: Selector = Field(min_length=1, max_length=80)
    property: Literal["color", "background-color"]
    colors: tuple[str, ...] = Field(min_length=1, max_length=32)


class TextExemption(ImmutableModel):
    selector: Selector = Field(min_length=1, max_length=80)
    reason: Literal["logotype", "pure_decoration"]


class VisualManifest(ImmutableModel):
    brand_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    approved: bool
    active: bool
    source_id: str = Field(min_length=1, max_length=100)
    source_version: str = Field(min_length=1, max_length=100)
    source_text: str = Field(min_length=1, max_length=10000)
    source_excerpt: str = Field(min_length=1, max_length=2000)
    logo_selectors: tuple[Selector, ...] = Field(default=(), max_length=16)
    logo_sha256: tuple[str, ...] = Field(default=(), max_length=32)
    palette: tuple[PaletteTarget, ...] = Field(default=(), max_length=32)
    text_exemptions: tuple[TextExemption, ...] = Field(default=(), max_length=16)


class VisualFinding(ImmutableModel):
    check: Literal["logo", "palette", "contrast", "alt_text"]
    rule_version: str
    element: str
    evidence_status: EvidenceStatus
    result: str
    explanation: str
    evidence: dict[str, str | int | float | bool | None]


class VisualResponse(ImmutableModel):
    schema_version: Literal["1.0"] = "1.0"
    mode: Literal["static_declarations"] = "static_declarations"
    brand_id: str
    draft_id: str
    draft_version: str
    input_sha256: str
    manifest_version: str
    manifest_sha256: str
    source_id: str
    source_version: str
    source_excerpt: str
    assets_sha256: dict[str, str]
    findings: tuple[VisualFinding, ...]
    limitations: tuple[str, ...]
