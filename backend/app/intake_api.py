"""Local PDF/image workflow routes; HTTP concerns stay out of extraction."""

import asyncio
from datetime import UTC, datetime
import importlib.metadata
import shutil
import subprocess
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile
from starlette.responses import JSONResponse

from app.domain import ReviewDecision
from app.intake_models import (ConfirmExtractionRequest, ExtractionCreated, ExtractionResponse,
                               ExtractionVersion, VersionRequest)
from app.schemas import AnalyzeResponse, ReviewDecisionRequest, ReviewDecisionResponse, ReviewRunSummary
from app.services.extraction_store import ExtractionStore


class IntakeBodyLimitMiddleware:
    """Bound requests before multipart parsing/spooling and mark private responses."""

    def __init__(self, app):
        self.app = app
        self.uploads = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        private = path.startswith(("/api/intake", "/api/reviews"))
        original_send = send

        async def send_private(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([
                    (b"cache-control", b"no-store"), (b"pragma", b"no-cache"),
                    (b"x-content-type-options", b"nosniff"), (b"vary", b"Authorization"),
                ])
            await original_send(message)

        if private:
            send = send_private
        if scope["method"] != "POST" or not (private or path == "/api/reviews/analyze-document"):
            return await self.app(scope, receive, send)
        maximum = 5 * 1024 * 1024 + 16 * 1024 if path in ("/api/intake", "/api/reviews/analyze-document") else 416 * 1024
        if self.uploads >= 2:
            return await JSONResponse({"detail": "Upload capacity is full. Retry later."}, status_code=429)(scope, receive, send)
        self.uploads += 1
        try:
            chunks = []
            size = 0
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    size += len(message.get("body", b""))
                    if size > maximum:
                        return await JSONResponse({"detail": "Request exceeds the upload or correction size limit."}, status_code=413)(scope, receive, send)
                    chunks.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
            body = b"".join(chunks)

            async def bounded_receive():
                nonlocal body
                if body is not None:
                    value, body = body, None
                    return {"type": "http.request", "body": value, "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, send)
        except TimeoutError:
            await JSONResponse({"detail": "Upload timed out. Retry with a smaller file."}, status_code=408)(scope, receive, send)
        finally:
            self.uploads -= 1


def build_intake_router(store: ExtractionStore) -> APIRouter:
    router = APIRouter(prefix="/api/intake", tags=["Local document intake"])

    def enabled() -> None:
        if not store.settings.intake_enabled:
            raise HTTPException(503, "Local PDF/image intake is disabled. Enable PRAMANA_ENABLE_LOCAL_INTAKE=1 for fictional demo files.")

    def token(authorization: str | None) -> str:
        enabled()
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 128:
            raise HTTPException(404, "Extraction not found or access has expired.")
        return authorization[7:]

    @router.get("/health")
    def readiness():
        executable = shutil.which(store.settings.tesseract_cmd)
        ocr_ready = False
        version = None
        if executable:
            command = [executable, "--list-langs"]
            if store.settings.tessdata_dir:
                command += ["--tessdata-dir", store.settings.tessdata_dir]
            try:
                result = subprocess.run(command, capture_output=True, timeout=3, check=True)
                ocr_ready = "eng" in result.stdout.decode("utf-8", "replace").splitlines()
                version = subprocess.run([executable, "--version"], capture_output=True,
                                         timeout=3, check=True).stdout.decode("utf-8", "replace").splitlines()[0]
            except (OSError, subprocess.SubprocessError, IndexError):
                pass
        return {"enabled": store.settings.intake_enabled, "ocr_ready": ocr_ready,
                "tesseract": version, "pypdfium2": importlib.metadata.version("pypdfium2"),
                "persistence": "volatile_local_demo", "limits": store.settings.intake_limits.model_dump(),
                "isolation": "process_limits_only_not_a_security_sandbox"}

    @router.post("", response_model=ExtractionCreated, status_code=202)
    async def upload(brand_id: Annotated[str, Form(min_length=1, max_length=100)],
                     file: Annotated[UploadFile, File()]):
        try:
            enabled()
            # This is the existing approved demo brand, not an organization/identity supplied by a client.
            if brand_id != "lumadesk":
                raise HTTPException(404, "No approved configuration exists for this brand.")
            content = await file.read(store.settings.intake_limits.max_bytes + 1)
            return store.create(file.filename, file.content_type, content, brand_id)
        finally:
            await file.close()

    @router.get("/{extraction_id}", response_model=ExtractionResponse)
    def status(extraction_id: str, authorization: Annotated[str | None, Header()] = None):
        return store.get(extraction_id, token(authorization))

    @router.get("/{extraction_id}/versions/{version}", response_model=ExtractionVersion)
    def version(extraction_id: str, version: int, authorization: Annotated[str | None, Header()] = None):
        return store.version(extraction_id, token(authorization), version)

    @router.get("/{extraction_id}/pages/{page}/preview")
    def preview(extraction_id: str, page: int, authorization: Annotated[str | None, Header()] = None):
        return Response(store.preview(extraction_id, token(authorization), page), media_type="image/png")

    @router.get("/{extraction_id}/original")
    def original(extraction_id: str, authorization: Annotated[str | None, Header()] = None):
        return Response(store.original(extraction_id, token(authorization)), media_type="application/octet-stream",
                        headers={"Content-Disposition": 'attachment; filename="original-upload"'})

    @router.post("/{extraction_id}/cancel", response_model=ExtractionResponse)
    def cancel(extraction_id: str, authorization: Annotated[str | None, Header()] = None):
        return store.cancel(extraction_id, token(authorization))

    @router.post("/{extraction_id}/confirm", response_model=ExtractionResponse)
    def confirm(extraction_id: str, request: ConfirmExtractionRequest,
                authorization: Annotated[str | None, Header()] = None):
        return store.confirm(extraction_id, token(authorization), request)

    @router.post("/{extraction_id}/analyze", response_model=AnalyzeResponse)
    def analyze(extraction_id: str, request: VersionRequest,
                authorization: Annotated[str | None, Header()] = None):
        return store.analyze(extraction_id, token(authorization), request)

    @router.get("/{extraction_id}/reviews/{run_id}", response_model=ReviewRunSummary)
    def review(extraction_id: str, run_id: str, authorization: Annotated[str | None, Header()] = None):
        with store.lock:
            job = store.current_review_job(extraction_id, token(authorization), run_id)
            return ReviewRunSummary.from_domain(job.reviews.get_review_record(run_id))

    @router.post("/{extraction_id}/reviews/{run_id}/decision", response_model=ReviewDecisionResponse)
    def decide(extraction_id: str, run_id: str, request: ReviewDecisionRequest,
               authorization: Annotated[str | None, Header()] = None):
        with store.lock:
            job = store.current_review_job(extraction_id, token(authorization), run_id)
            record = job.reviews.record_review_decision(run_id, ReviewDecision(request.decision), datetime.now(UTC))
            return ReviewDecisionResponse.from_domain(run_id, record)

    return router
