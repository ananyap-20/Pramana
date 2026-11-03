"""Bounded private static-check endpoint; no persistence or approval side effects."""

import asyncio
import os
import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.repositories.visual_manifest import VisualManifestRepository
from app.services.visual_process import run_visual, VisualProblem
from app.visual_models import VisualError, VisualRequest, VisualResponse


class VisualRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid visual request. Check the schema and input limits.") from None

        return safe_handler


class VisualBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/visual/analyze":
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")])
            await send(message)

        if scope["method"] != "POST":
            return await self.app(scope, receive, private_send)
        if self.active >= 1:
            return await JSONResponse({"detail": "Visual capacity is full. Retry later."}, 429)(scope, receive, private_send)
        self.active += 1
        try:
            chunks, size = [], 0
            try:
                async with asyncio.timeout(5):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        size += len(chunk)
                        if size > 768 * 1024:
                            return await JSONResponse({"detail": "Visual request exceeds 768 KiB."}, 413)(scope, receive, private_send)
                        chunks.append(chunk)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await JSONResponse({"detail": "Visual upload timed out."}, 408)(scope, receive, private_send)
            body = b"".join(chunks)

            async def bounded_receive():
                nonlocal body
                if body is not None:
                    value, body = body, None
                    return {"type": "http.request", "body": value, "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, private_send)
        finally:
            self.active -= 1


def build_visual_router() -> APIRouter:
    manifests = VisualManifestRepository(os.getenv("PRAMANA_VISUAL_MANIFEST_PATH") or None)
    router = APIRouter(prefix="/api/visual", tags=["Visual checks"], route_class=VisualRoute)

    @router.get("/demo", response_model=VisualRequest)
    def demo():
        manifest = manifests.get("lumadesk")
        if manifest is None or manifest.source_id != "lumadesk-demo-visual-policy":
            raise HTTPException(404, "The fictional demo policy is not active.")
        asset = Path(__file__).with_name("data") / "lumadesk-demo.png"
        return VisualRequest(brand_id="lumadesk", draft_id="fictional-visual-demo", draft_version="v1", mode="rendered",
            html='<main><img id="logo" src="asset:demo_logo" alt="Fictional LumaDesk demo mark"><h1 class="brand">A thoughtful review.</h1><p class="brand">Evidence informs. Humans decide.</p></main>',
            css='main { color:#1c1c18; background-color:#fcf9f2; padding:24px; font-family:Arial,sans-serif; } h1 { font-size:28px; } p { font-size:16px; }',
            assets=({"asset_id":"demo_logo","media_type":"image/png","content_base64":base64.b64encode(asset.read_bytes()).decode()},))

    @router.post("/analyze", response_model=VisualResponse,
                 responses={status: {"model": VisualError} for status in (404, 408, 413, 422, 429, 503)})
    async def analyze(request: VisualRequest) -> VisualResponse:
        manifest = manifests.get(request.brand_id)
        if manifest is None:
            raise HTTPException(404, "No active approved visual manifest exists for this brand.")
        try:
            return await run_in_threadpool(run_visual, request, manifest)
        except VisualProblem as error:
            raise HTTPException(error.status, str(error)) from None

    return router
