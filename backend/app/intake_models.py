"""Versioned transcription provenance, independent of brand evidence statuses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IntakeLimits(ImmutableModel):
    max_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=5 * 1024 * 1024)
    max_pages: int = Field(default=10, ge=1, le=10)
    max_pixels: int = Field(default=12_000_000, ge=1, le=12_000_000)
    max_total_pixels: int = Field(default=60_000_000, ge=1, le=60_000_000)
    render_dpi: int = Field(default=200, ge=72, le=300)
    max_characters: int = Field(default=100_000, ge=1, le=100_000)
    max_output_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    max_regions: int = Field(default=20_000, ge=1, le=20_000)
    max_jobs: int = Field(default=8, ge=1, le=8)
    concurrency: int = Field(default=1, ge=1, le=2)
    timeout_seconds: float = Field(default=60, gt=0, le=120)
    ttl_seconds: float = Field(default=900, gt=0, le=1800)
    memory_mib: int = Field(default=768, ge=128, le=1024)
    max_versions: int = Field(default=10, ge=2, le=10)


class TextRegion(ImmutableModel):
    start: int
    end: int
    bounds: tuple[float, float, float, float] | None = None
    confidence: float | None = None


class ExtractedPage(ImmutableModel):
    page: int
    text: str
    start: int
    end: int
    method: Literal["pdf_text", "ocr", "human_edited"]
    width: float
    height: float
    coordinates: Literal["pdf_points_bottom_left", "pixels_top_left", "none"]
    rotation: int = 0
    regions: tuple[TextRegion, ...] = ()
    warnings: tuple[str, ...] = ()


class ExtractionVersion(ImmutableModel):
    version: int
    text_sha256: str
    text: str
    pages: tuple[ExtractedPage, ...]
    created_at: datetime
    human_edited: bool = False
    parent_version: int | None = None


class ExtractionResult(ImmutableModel):
    pages: tuple[ExtractedPage, ...]
    tools: dict[str, str]
    settings: dict[str, str | int]
    warnings: tuple[str, ...]


class Confirmation(ImmutableModel):
    version: int
    text_sha256: str
    confirmed_at: datetime
    actor: None = None
    actor_kind: Literal["anonymous_capability_holder"] = "anonymous_capability_holder"


class ExtractionResponse(BaseModel):
    extraction_id: str
    state: Literal["queued", "processing", "needs_confirmation", "ready", "failed", "expired"]
    filename: str
    file_type: str
    file_sha256: str
    expires_at: datetime
    current: ExtractionVersion | None = None
    confirmation: Confirmation | None = None
    tools: dict[str, str] = Field(default_factory=dict)
    settings: dict[str, str | int] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error: str | None = None
    extraction_seconds: float | None = None
    persistence: Literal["volatile_local_demo"] = "volatile_local_demo"


class ExtractionCreated(ExtractionResponse):
    access_token: str


class VersionRequest(ImmutableModel):
    version: int = Field(ge=1)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ConfirmExtractionRequest(VersionRequest):
    # Corrections remain page-scoped; coordinates for changed pages are discarded.
    page_texts: tuple[str, ...] = Field(min_length=1, max_length=10)
    confirm_transcription: Literal[True]


class DocumentProvenance(ImmutableModel):
    extraction_id: str
    file_sha256: str
    file_type: str
    version: int
    text_sha256: str
    human_edited: bool
    confirmed_at: datetime
    actor: None = None
    actor_kind: str = "anonymous_capability_holder"
    tools: dict[str, str]
    settings: dict[str, str | int]
    pages: tuple[ExtractedPage, ...]
    original_available_until: datetime
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"
