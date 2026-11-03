"""Shared retained audit routes, isolated from historical account collections."""

from dataclasses import asdict
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from app.audit_models import AuditAnalytics, AuditAnalyzeRequest, AuditDecisionRequest, AuditError, AuditEvent, AuditHistory, AuditRun, AuditSnapshot
from app.intake_models import VersionRequest
from app.repositories.audit_repository import AuditRepository
from app.repositories.demo_repository import InMemoryDemoRepository
from app.schemas import AnalyzeResponse, EvidenceReceiptResponse
from app.services.audit_security import AuditPrincipal, SnapshotCipher
from app.services.document_intake import DocumentIntakeError, DocumentIntakeTooLargeError, MAX_DOCX_BYTES, extract_docx_isolated, validate_docx_media_type
from app.services.review_service import UnknownBrandError, analyze_draft
from app.services.bunny_storage import BunnyStorage
from app.services.retained_files import RetainedFiles


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def request_key(value: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100,
                                           pattern=r"^[A-Za-z0-9_-]+$")]) -> str:
    return value


def principal(request: Request) -> AuditPrincipal:
    return request.state.audit_principal


class AuditRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid audit request. Check its fields and limits.") from None
        return safe_handler


class AuditRuntime:
    def __init__(self, settings, intake):
        self.intake = intake
        self.repository = None
        self.files = None
        self.legacy_files = []
        self.cleanup_task = None
        self.cleanup_failed = False
        storage = BunnyStorage.from_environment()
        if not os.getenv("PRAMANA_AUDIT_KEYS") and not os.getenv("PRAMANA_AUDIT_ACTIVE_KEY"):
            if storage or os.getenv("PRAMANA_REQUIRE_AUDIT") == "1" or os.getenv("PRAMANA_REQUIRE_BUNNY") == "1":
                raise ValueError("Retained audit requires MongoDB and encryption configuration.")
            return
        if not settings.mongodb_uri:
            raise ValueError("Retained audit requires MongoDB; memory fallback is not supported.")
        cipher = SnapshotCipher(os.getenv("PRAMANA_AUDIT_KEYS", ""), os.getenv("PRAMANA_AUDIT_ACTIVE_KEY", ""))
        try:
            days = int(os.getenv("PRAMANA_AUDIT_RETENTION_DAYS", "30"))
        except ValueError:
            raise ValueError("Audit retention must be an integer from 1 to 90 days.") from None
        self.repository = AuditRepository(settings.mongodb_uri, settings.mongodb_db, cipher, days)
        # Preserve historical private collections; new shared records stay separate.
        self.repository.collection = self.repository.collection.database.get_collection("public_reviews_v1",
            write_concern=self.repository.collection.write_concern, read_concern=self.repository.collection.read_concern)
        self.repository.files_collection = "public_files_v1"
        if storage:
            self.files = RetainedFiles(self.repository, storage)
            self.legacy_files = [RetainedFiles(self.repository, storage, collection_name=name)
                                 for name in ("audit_files_v1", "identity_files_v1")]
        if os.getenv("PRAMANA_REQUIRE_BUNNY") == "1" and self.files is None:
            raise ValueError("Deployment requires Bunny Storage configuration.")

    def start(self):
        if self.repository:
            self.repository.start()
        if self.files:
            self.files.start()
        for files in self.legacy_files:
            files.start()

    def sweep_files(self):
        if self.files:
            self.files.sweep()
        for files in self.legacy_files:
            files.sweep()

    async def start_cleanup(self):
        if self.files:
            self.cleanup_task = asyncio.create_task(self.cleanup_loop())

    async def cleanup_loop(self):
        while True:
            try:
                await run_in_threadpool(self.sweep_files)
                self.cleanup_failed = False
            except Exception:
                # Preserve cleanup references for retry; readiness checks provider availability.
                self.cleanup_failed = True
                logging.getLogger(__name__).warning("Private file cleanup failed; retained references will be retried.")
            await asyncio.sleep(60)

    async def stop_cleanup(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    def close(self):
        if self.repository:
            self.repository.close()

    def store_analysis(self, identity, key, fingerprint, analysis):
        repository = self.repository
        configuration = InMemoryDemoRepository().get_brand(analysis.brand_id)
        if configuration is None:
            raise HTTPException(404, "No approved brand configuration exists.")
        analysis = analysis.model_copy(update={"persistence": "mongodb_encrypted_audit"})
        config = asdict(configuration)
        snapshot = AuditSnapshot(analysis=analysis, configuration=config)
        document = repository.save(identity, key, fingerprint, snapshot,
            [{"category": f.category, "rule_id": f.rule_id, "rule_version": f.rule_version,
              "source_id": f.source_id, "source_version": f.source_version, "evidence_status": f.evidence_status}
             for f in analysis.findings], digest(config))
        return repository.snapshot(identity, document).analysis

    def analyze(self, identity, key, fingerprint, brand_id, text, input_type, paragraph_count=None):
        existing = self.repository.existing(identity, key, fingerprint)
        if existing:
            return self.repository.snapshot(identity, existing).analysis
        ephemeral = InMemoryDemoRepository()
        try:
            run, receipts = analyze_draft(draft_text=text, brand_id=brand_id,
                configuration_repository=ephemeral, review_run_repository=ephemeral)
        except UnknownBrandError:
            raise HTTPException(404, "No approved brand configuration exists.") from None
        result = AnalyzeResponse(review_run_id=run.review_run_id, brand_id=run.brand_id,
            draft_id=run.draft.draft_id, draft_version=run.draft.version, evaluated_at=run.evaluated_at,
            persistence="mongodb_encrypted_audit", input_type=input_type, draft_text=run.draft.text,
            paragraph_count=paragraph_count, findings=[EvidenceReceiptResponse.from_domain(r) for r in receipts])
        return self.store_analysis(identity, key, fingerprint, result)

    def router(self):
        router = APIRouter(prefix="/api/audit", tags=["Retained audit"], route_class=AuditRoute,
                           responses={status: {"model": AuditError} for status in (401, 403, 404, 408, 409, 413, 422, 429, 503)})
        repository = self.repository

        @router.post("/reviews/analyze", response_model=AnalyzeResponse)
        def analyze(request: AuditAnalyzeRequest, identity: Annotated[AuditPrincipal, Depends(principal)], key: Annotated[str, Depends(request_key)]):
            if not request.draft_text.strip() or "\x00" in request.draft_text or any(0xD800 <= ord(c) <= 0xDFFF for c in request.draft_text):
                raise HTTPException(422, "Draft must contain readable Unicode text.")
            fingerprint = digest(["text-v1", identity.actor_id, request.model_dump()])
            return self.analyze(identity, key, fingerprint, request.brand_id, request.draft_text, "plain_text")

        @router.post("/reviews/analyze-document", response_model=AnalyzeResponse)
        async def document(brand_id: Annotated[str, Form(min_length=1, max_length=100)], file: UploadFile,
                           identity: Annotated[AuditPrincipal, Depends(principal)], key: Annotated[str, Depends(request_key)]):
            try:
                content = await file.read(MAX_DOCX_BYTES + 1)
                if len(content) > MAX_DOCX_BYTES:
                    raise HTTPException(413, "DOCX exceeds 5 MiB.")
                fingerprint = digest(["docx-v1", identity.actor_id, brand_id, file.filename, hashlib.sha256(content).hexdigest()])
                def process():
                    existing = repository.existing(identity, key, fingerprint)
                    if existing:
                        result = repository.snapshot(identity, existing).analysis
                        if self.files:
                            self.files.save(identity, result.review_run_id, content)
                        return result
                    validate_docx_media_type(file.content_type)
                    extracted = extract_docx_isolated(file.filename, content)
                    result = self.analyze(identity, key, fingerprint, brand_id, extracted.text, "docx", extracted.paragraph_count)
                    if self.files:
                        self.files.save(identity, result.review_run_id, content)
                    return result
                return await run_in_threadpool(process)
            except DocumentIntakeTooLargeError as error:
                raise HTTPException(413, str(error)) from None
            except DocumentIntakeError as error:
                raise HTTPException(422, str(error)) from None
            finally:
                await file.close()

        @router.post("/intake/{extraction_id}/analyze", response_model=AnalyzeResponse)
        def confirmed_document(extraction_id: str, request: VersionRequest,
                               identity: Annotated[AuditPrincipal, Depends(principal)], key: Annotated[str, Depends(request_key)],
                               upload_token: Annotated[str, Header(alias="X-Intake-Token", min_length=1, max_length=256)]):
            fingerprint = digest(["intake-v1", identity.actor_id, extraction_id, request.model_dump()])
            existing = repository.existing(identity, key, fingerprint)
            if existing:
                result = repository.snapshot(identity, existing).analysis
                if self.files:
                    self.files.save(identity, result.review_run_id, self.intake.original(extraction_id, upload_token))
                return result
            analysis = self.intake.analyze(extraction_id, upload_token, request)
            result = self.store_analysis(identity, key, fingerprint, analysis)
            if self.files:
                self.files.save(identity, result.review_run_id, self.intake.original(extraction_id, upload_token))
            return result

        @router.get("/reviews/{run_id}/original")
        def original(run_id: str, identity: Annotated[AuditPrincipal, Depends(principal)]):
            if self.files is None:
                raise HTTPException(503, "Private file storage is not configured.")
            return Response(self.files.original(identity, run_id), media_type="application/octet-stream",
                headers={"Content-Disposition": 'attachment; filename="original.bin"'})

        @router.get("/reviews/history/{brand_id}", response_model=AuditHistory)
        def history(brand_id: str, identity: Annotated[AuditPrincipal, Depends(principal)],
                    limit: Annotated[int, Query(ge=1, le=100)] = 25,
                    cursor: Annotated[str | None, Query(max_length=100)] = None):
            documents, next_cursor = repository.history(identity, brand_id, limit, cursor)
            return AuditHistory(records=tuple(repository.summary(d) for d in documents), next_cursor=next_cursor)

        @router.get("/reviews/{run_id}", response_model=AuditRun)
        def review(run_id: str, identity: Annotated[AuditPrincipal, Depends(principal)]):
            return repository.summary(repository.get(identity, run_id))

        @router.get("/reviews/{run_id}/snapshot", response_model=AuditSnapshot)
        def snapshot(run_id: str, identity: Annotated[AuditPrincipal, Depends(principal)]):
            return repository.snapshot(identity, repository.get(identity, run_id, with_snapshot=True))

        @router.post("/reviews/{run_id}/decision", response_model=AuditEvent)
        def decision(run_id: str, request: AuditDecisionRequest,
                     identity: Annotated[AuditPrincipal, Depends(principal)], key: Annotated[str, Depends(request_key)]):
            fingerprint = digest(["decision-v1", identity.actor_id, request.model_dump()])
            return repository.decision(identity, run_id, key, fingerprint, request.decision, request.expected_revision)

        @router.get("/analytics/{brand_id}", response_model=AuditAnalytics)
        def analytics(brand_id: str, identity: Annotated[AuditPrincipal, Depends(principal)],
                      start: datetime | None = None, end: datetime | None = None,
                      days: Annotated[int, Query(ge=1, le=90)] = 30):
            now = datetime.now(UTC)
            start, end = start or now - timedelta(days=days), end or now
            if start.tzinfo is None or end.tzinfo is None or not start < end or end - start > timedelta(days=90) or end > now:
                raise HTTPException(422, "Use an ordered UTC-aware period of at most 90 days ending no later than now.")
            start, end = start.astimezone(UTC), end.astimezone(UTC)
            counts = repository.aggregate(identity, brand_id, start, end, now)
            totals = counts["totals"][0] if counts["totals"] else {"runs": 0, "findings": 0, "events": 0}
            outcomes = {key: 0 for key in ("pending", "approved", "revision", "rejected")}
            outcomes.update({d["_id"]: d["count"] for d in counts["outcomes"]})
            return AuditAnalytics(brand_id=brand_id, period_start=start, period_end=end, generated_at=datetime.now(UTC),
                total_runs=totals["runs"], total_findings=totals["findings"], decision_events=totals["events"], outcomes=outcomes,
                categories={d["_id"]: d["count"] for d in counts["categories"]},
                repeated_rules=tuple({**d["_id"], "count": d["count"]} for d in counts["rules"]),
                daily=tuple({"date": d["_id"], "runs": d["runs"], "findings": d["findings"]} for d in counts["daily"]),
                definition="Completed retained analyses evaluated in [start,end), UTC. Pending means no human decision. Outcomes are latest decisions; event count includes all decisions for this cohort. Failed/in-progress extractions, expired/deleted runs, visual-only checks and legacy demo history are excluded. Category/rule counts use validated findings, not real-world accuracy. One majority-read aggregation; generated_at is response freshness, not a historical decision cutoff.")

        return router
