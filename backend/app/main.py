"""ASGI application for Pramana's fictional Day 1 demo."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.domain import ReviewDecision
from app.repositories.demo_repository import (
    InMemoryDemoRepository,
    UnknownReviewRunError,
)
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DemoConfigResponse,
    DemoRuleResponse,
    EvidenceReceiptResponse,
    HealthResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewRunSummary,
)
from app.services.review_service import UnknownBrandError, analyze_draft
from app.services.document_intake import (
    DocumentIntakeError,
    DocumentIntakeTooLargeError,
    MAX_DOCX_BYTES,
    extract_docx_bytes,
)


def create_app() -> FastAPI:
    settings = get_settings()
    repository = InMemoryDemoRepository()
    app = FastAPI(
        title="Pramana Day 1 Demo API",
        version="0.1.0",
        description="Fictional deterministic evidence-validation demo. Not durable persistence.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", persistence="in_memory_demo_not_durable")

    @app.get("/api/demo/config/{brand_id}", response_model=DemoConfigResponse)
    def demo_config(brand_id: str) -> DemoConfigResponse:
        configuration = repository.get_brand(brand_id)
        if configuration is None:
            raise HTTPException(status_code=404, detail="No approved configuration exists for this brand.")
        return DemoConfigResponse(
            brand_id=configuration.brand_id,
            brand_name=configuration.brand_name,
            rules=[
                DemoRuleResponse(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    category=rule.category.value,
                    description=rule.description,
                    source_id=rule.source_id,
                    source_version=rule.source_version,
                )
                for rule in configuration.rules
                if rule.active
            ],
        )

    @app.post("/api/reviews/analyze", response_model=AnalyzeResponse)
    def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
        try:
            review_run, receipts = analyze_draft(
                draft_text=request.draft_text,
                brand_id=request.brand_id,
                configuration_repository=repository,
                review_run_repository=repository,
            )
        except UnknownBrandError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return AnalyzeResponse(
            review_run_id=review_run.review_run_id,
            brand_id=review_run.brand_id,
            draft_id=review_run.draft.draft_id,
            draft_version=review_run.draft.version,
            evaluated_at=review_run.evaluated_at,
            persistence="in_memory_demo_not_durable",
            input_type="plain_text",
            draft_text=review_run.draft.text,
            findings=[EvidenceReceiptResponse.from_domain(receipt) for receipt in receipts],
        )

    @app.post("/api/reviews/analyze-document", response_model=AnalyzeResponse)
    async def analyze_document(
        brand_id: Annotated[str, Form(min_length=1, max_length=100)],
        file: Annotated[UploadFile, File(description="A .docx draft up to 5 MiB")],
    ) -> AnalyzeResponse:
        content = await file.read(MAX_DOCX_BYTES + 1)
        if len(content) > MAX_DOCX_BYTES:
            raise HTTPException(status_code=413, detail="The uploaded document exceeds the 5 MiB limit.")
        try:
            extracted = extract_docx_bytes(file.filename, content)
            review_run, receipts = analyze_draft(
                draft_text=extracted.text,
                brand_id=brand_id,
                configuration_repository=repository,
                review_run_repository=repository,
            )
        except DocumentIntakeTooLargeError as error:
            raise HTTPException(status_code=413, detail=str(error)) from error
        except DocumentIntakeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except UnknownBrandError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        finally:
            await file.close()

        return AnalyzeResponse(
            review_run_id=review_run.review_run_id,
            brand_id=review_run.brand_id,
            draft_id=review_run.draft.draft_id,
            draft_version=review_run.draft.version,
            evaluated_at=review_run.evaluated_at,
            persistence="in_memory_demo_not_durable",
            input_type="docx",
            draft_text=review_run.draft.text,
            paragraph_count=extracted.paragraph_count,
            findings=[EvidenceReceiptResponse.from_domain(receipt) for receipt in receipts],
        )

    @app.post(
        "/api/reviews/{review_run_id}/decision",
        response_model=ReviewDecisionResponse,
    )
    def record_review_decision(
        review_run_id: str, request: ReviewDecisionRequest
    ) -> ReviewDecisionResponse:
        try:
            decision = repository.record_review_decision(
                review_run_id,
                ReviewDecision(request.decision),
                datetime.now(UTC),
            )
        except UnknownReviewRunError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return ReviewDecisionResponse.from_domain(review_run_id, decision)

    @app.get(
        "/api/reviews/history/{brand_id}",
        response_model=list[ReviewRunSummary],
    )
    def review_history(brand_id: str) -> list[ReviewRunSummary]:
        """Return summaries of past review runs for a brand (most recent first)."""
        configuration = repository.get_brand(brand_id)
        if configuration is None:
            raise HTTPException(
                status_code=404,
                detail="No approved configuration exists for this brand.",
            )
        records = repository.list_review_runs(brand_id)
        return [ReviewRunSummary.from_domain(record) for record in records]

    return app


app = create_app()
