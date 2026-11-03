"""Expiring local demo intake. Capabilities are possession checks, not user identity."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from pathlib import PurePosixPath
import re
import secrets
from threading import Event, RLock
import time
from uuid import uuid4

from app.config import Settings
from app.intake_models import (Confirmation, ConfirmExtractionRequest, DocumentProvenance,
                               ExtractionCreated, ExtractionResponse, ExtractionResult,
                               ExtractionVersion, VersionRequest)
from app.repositories.demo_repository import InMemoryDemoRepository
from app.schemas import AnalyzeResponse, EvidenceReceiptResponse
from app.services.document_intake import DocumentIntakeError
from app.services.intake_process import run_extraction
from app.services.review_service import analyze_draft


class IntakeProblem(ValueError):
    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(detail)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_upload(filename: str | None, mime: str | None, content: bytes, maximum: int) -> tuple[str, str]:
    if not content:
        raise IntakeProblem(422, "The uploaded file is empty.")
    if len(content) > maximum:
        raise IntakeProblem(413, "The upload exceeds the configured byte limit (at most 5 MiB).")
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    suffix = PurePosixPath(name).suffix.lower()
    formats = {".pdf": ("pdf", "application/pdf", b"%PDF-"),
               ".png": ("png", "image/png", b"\x89PNG\r\n\x1a\n"),
               ".jpg": ("jpeg", "image/jpeg", b"\xff\xd8\xff"),
               ".jpeg": ("jpeg", "image/jpeg", b"\xff\xd8\xff")}
    if suffix not in formats:
        raise IntakeProblem(422, "Choose a PDF, PNG or JPEG. DOCX uses the existing document-analysis endpoint.")
    kind, expected_mime, signature = formats[suffix]
    if mime not in (expected_mime, "application/octet-stream", "", None) or not content.startswith(signature):
        raise IntakeProblem(422, "The filename, declared type and file signature do not agree.")
    return re.sub(r"[^\w.() -]", "_", name)[:120], kind


@dataclass
class ExtractionJob:
    extraction_id: str
    token_digest: str
    filename: str
    kind: str
    file_digest: str
    content: bytes
    brand_id: str
    expires_at: datetime
    deadline: float
    state: str = "queued"
    versions: list[ExtractionVersion] = field(default_factory=list)
    result: ExtractionResult | None = None
    previews: dict[int, bytes] = field(default_factory=dict)
    confirmation: Confirmation | None = None
    error: str | None = None
    extraction_seconds: float | None = None
    cancelled: Event = field(default_factory=Event)
    task: asyncio.Task | None = None
    last_confirmation: str | None = None
    analysis: AnalyzeResponse | None = None
    # Uploaded drafts and even their run summaries stay out of shared history.
    reviews: InMemoryDemoRepository = field(default_factory=lambda: InMemoryDemoRepository(max_review_records=10))


class ExtractionStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs: dict[str, ExtractionJob] = {}
        self.lock = RLock()
        self.reaper: asyncio.Task | None = None

    async def start(self) -> None:
        self.reaper = asyncio.create_task(self._reap())

    async def close(self) -> None:
        if self.reaper:
            self.reaper.cancel()
            await asyncio.gather(self.reaper, return_exceptions=True)
        tasks = []
        with self.lock:
            for job in self.jobs.values():
                job.cancelled.set()
                if job.task:
                    tasks.append(job.task)
        await asyncio.gather(*tasks, return_exceptions=True)
        self.jobs.clear()

    def _expire(self, job: ExtractionJob) -> None:
        job.cancelled.set()
        job.state = "expired"
        job.content = b""
        job.versions.clear()
        job.previews.clear()
        job.result = None
        job.analysis = None
        job.confirmation = None
        job.last_confirmation = None
        job.error = None
        job.reviews = InMemoryDemoRepository(max_review_records=10)

    async def _reap(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            with self.lock:
                for key, job in list(self.jobs.items()):
                    if time.monotonic() >= job.deadline:
                        self._expire(job)
                        # Keep a short, bounded tombstone for an actionable expired state.
                        if time.monotonic() >= job.deadline + 60 and (not job.task or job.task.done()):
                            del self.jobs[key]

    def _lookup(self, extraction_id: str, token: str) -> ExtractionJob:
        job = self.jobs.get(extraction_id)
        if job is None or not hmac.compare_digest(job.token_digest, digest(token.encode())):
            raise IntakeProblem(404, "Extraction not found or access has expired.")
        if time.monotonic() >= job.deadline and job.state != "expired":
            self._expire(job)
        return job

    def _active(self, extraction_id: str, token: str) -> ExtractionJob:
        job = self._lookup(extraction_id, token)
        if job.state == "expired":
            raise IntakeProblem(410, "This extraction has expired. Upload the original again.")
        return job

    def snapshot(self, job: ExtractionJob) -> ExtractionResponse:
        return ExtractionResponse(
            extraction_id=job.extraction_id, state=job.state, filename=job.filename, file_type=job.kind,
            file_sha256=job.file_digest, expires_at=job.expires_at,
            current=job.versions[-1] if job.versions else None, confirmation=job.confirmation,
            tools=job.result.tools if job.result else {}, settings=job.result.settings if job.result else {},
            warnings=job.result.warnings if job.result else (), error=job.error,
            extraction_seconds=job.extraction_seconds,
        )

    def get(self, extraction_id: str, token: str) -> ExtractionResponse:
        with self.lock:
            return self.snapshot(self._lookup(extraction_id, token))

    def create(self, filename: str | None, mime: str | None, content: bytes, brand_id: str) -> ExtractionCreated:
        limits = self.settings.intake_limits
        filename, kind = validate_upload(filename, mime, content, limits.max_bytes)
        with self.lock:
            for key, job in list(self.jobs.items()):
                if time.monotonic() >= job.deadline:
                    self._expire(job)
                    if not job.task or job.task.done():
                        del self.jobs[key]
            if len(self.jobs) >= limits.max_jobs or sum(bool(j.task and not j.task.done()) for j in self.jobs.values()) >= limits.concurrency:
                raise IntakeProblem(429, "The local extraction capacity is full. Cancel an unused extraction or retry later.")
            token = secrets.token_urlsafe(32)
            job = ExtractionJob(str(uuid4()), digest(token.encode()), filename, kind, digest(content), content,
                                brand_id, datetime.now(UTC) + timedelta(seconds=limits.ttl_seconds),
                                time.monotonic() + limits.ttl_seconds)
            self.jobs[job.extraction_id] = job
            job.task = asyncio.create_task(self._extract(job))
            return ExtractionCreated(**self.snapshot(job).model_dump(), access_token=token)

    async def _extract(self, job: ExtractionJob) -> None:
        started = time.monotonic()
        with self.lock:
            if job.state == "expired":
                return
            job.state = "processing"
        try:
            result, previews = await asyncio.to_thread(
                run_extraction, job.content, job.kind, self.settings.intake_limits,
                self.settings.tesseract_cmd, self.settings.tessdata_dir, job.cancelled,
            )
            with self.lock:
                if job.cancelled.is_set() or time.monotonic() >= job.deadline:
                    self._expire(job)
                    return
                text = "\n\n".join(p.text for p in result.pages)
                job.versions.append(ExtractionVersion(version=1, text=text, text_sha256=digest(text.encode()),
                                                       pages=result.pages, created_at=datetime.now(UTC)))
                job.result = result
                job.previews = previews
                job.state = "needs_confirmation"
        except DocumentIntakeError as error:
            with self.lock:
                if not job.cancelled.is_set():
                    job.state = "failed"
                    job.error = str(error)
                    job.content = b""
        except Exception:
            with self.lock:
                if not job.cancelled.is_set():
                    job.state = "failed"
                    job.error = "Extraction failed safely. Retry with a smaller valid file."
                    job.content = b""
        finally:
            job.extraction_seconds = round(time.monotonic() - started, 4)

    def cancel(self, extraction_id: str, token: str) -> ExtractionResponse:
        with self.lock:
            job = self._lookup(extraction_id, token)
            self._expire(job)
            job.deadline = time.monotonic()
            return self.snapshot(job)

    def version(self, extraction_id: str, token: str, number: int) -> ExtractionVersion:
        with self.lock:
            job = self._active(extraction_id, token)
            for version in job.versions:
                if version.version == number:
                    return version
            raise IntakeProblem(404, "That immutable extraction version was not found.")

    def preview(self, extraction_id: str, token: str, number: int) -> bytes:
        with self.lock:
            job = self._active(extraction_id, token)
            if number not in job.previews:
                raise IntakeProblem(404, "The page preview is not available.")
            return job.previews[number]

    def original(self, extraction_id: str, token: str) -> bytes:
        with self.lock:
            job = self._active(extraction_id, token)
            if not job.content:
                raise IntakeProblem(404, "The original is no longer retained.")
            return job.content

    @staticmethod
    def _check_version(job: ExtractionJob, request: VersionRequest) -> ExtractionVersion:
        if job.state not in ("needs_confirmation", "ready") or not job.versions:
            raise IntakeProblem(409, "Extraction is not available for confirmation or analysis.")
        current = job.versions[-1]
        if request.version != current.version or request.text_sha256 != current.text_sha256:
            raise IntakeProblem(409, "The extraction version has changed. Reload its preview and confirm again.")
        return current

    def confirm(self, extraction_id: str, token: str, request: ConfirmExtractionRequest) -> ExtractionResponse:
        with self.lock:
            job = self._active(extraction_id, token)
            request_digest = digest(request.model_dump_json().encode())
            if job.last_confirmation == request_digest and job.state == "ready":
                return self.snapshot(job)
            current = self._check_version(job, request)
            if len(request.page_texts) != len(current.pages):
                raise IntakeProblem(422, "Provide the text for every extracted page in order.")
            text = "\n\n".join(request.page_texts)
            if not text.strip() or "\x00" in text or any(0xD800 <= ord(c) <= 0xDFFF for c in text):
                raise IntakeProblem(422, "Confirmed text must be readable Unicode without null characters.")
            if len(text) > self.settings.intake_limits.max_characters:
                raise IntakeProblem(413, "Corrected text exceeds the configured character limit.")
            if len(job.versions) >= self.settings.intake_limits.max_versions:
                raise IntakeProblem(409, "The version limit was reached. Upload the original for a new extraction.")
            pages = []
            offset = 0
            for page, corrected in zip(current.pages, request.page_texts, strict=True):
                changed = corrected != page.text
                shift = offset - page.start
                regions = () if changed else tuple(r.model_copy(update={"start": r.start + shift, "end": r.end + shift}) for r in page.regions)
                pages.append(page.model_copy(update={
                    "text": corrected, "start": offset, "end": offset + len(corrected),
                    "method": "human_edited" if changed else page.method,
                    "coordinates": "none" if changed else page.coordinates, "regions": regions,
                }))
                offset += len(corrected) + 2
            now = datetime.now(UTC)
            version = ExtractionVersion(version=current.version + 1, text=text, text_sha256=digest(text.encode()),
                                        pages=tuple(pages), created_at=now, parent_version=current.version,
                                        human_edited=any(p.method == "human_edited" for p in pages))
            job.versions.append(version)
            job.confirmation = Confirmation(version=version.version, text_sha256=version.text_sha256, confirmed_at=now)
            job.analysis = None
            job.last_confirmation = request_digest
            job.state = "ready"
            return self.snapshot(job)

    def analyze(self, extraction_id: str, token: str, request: VersionRequest) -> AnalyzeResponse:
        with self.lock:
            job = self._active(extraction_id, token)
            current = self._check_version(job, request)
            if job.state != "ready" or job.confirmation is None or job.confirmation.version != current.version:
                raise IntakeProblem(409, "Confirm the exact transcription before analysis. Confirmation is not content approval.")
            if job.analysis:
                return job.analysis
            run, receipts = analyze_draft(draft_text=current.text, brand_id=job.brand_id,
                                          configuration_repository=job.reviews, review_run_repository=job.reviews)
            provenance = DocumentProvenance(extraction_id=job.extraction_id, file_sha256=job.file_digest,
                                           file_type=job.kind, version=current.version, text_sha256=current.text_sha256,
                                           human_edited=current.human_edited, confirmed_at=job.confirmation.confirmed_at,
                                           tools=job.result.tools, settings=job.result.settings,
                                           pages=current.pages, original_available_until=job.expires_at)
            job.analysis = AnalyzeResponse(review_run_id=run.review_run_id, brand_id=run.brand_id,
                                           draft_id=run.draft.draft_id, draft_version=run.draft.version,
                                           evaluated_at=run.evaluated_at, persistence="volatile_local_demo",
                                           input_type=job.kind, draft_text=run.draft.text,
                                           findings=[EvidenceReceiptResponse.from_domain(r) for r in receipts],
                                           document_provenance=provenance)
            return job.analysis

    def current_review_job(self, extraction_id: str, token: str, run_id: str) -> ExtractionJob:
        # Call only while holding the store lock, including the subsequent decision mutation.
        job = self._active(extraction_id, token)
        if job.analysis is None or job.analysis.review_run_id != run_id:
            raise IntakeProblem(409, "This analysis is superseded or unavailable. Analyze the current confirmed version.")
        return job
