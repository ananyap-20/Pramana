"""Authenticate before body parsing; bound audit requests and sanitize failures."""

import asyncio
import os

from fastapi import HTTPException
from starlette.responses import JSONResponse


class AuditMiddleware:
    def __init__(self, app, runtime):
        self.app, self.runtime = app, runtime
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/reviews") and os.getenv("PRAMANA_REQUIRE_AUDIT") == "1":
            return await JSONResponse({"detail": "Connect your organization access key before reviewing."}, 403)(scope, receive, send)
        if scope["type"] != "http" or not scope["path"].startswith("/api/audit/"):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")])
            await send(message)

        if self.runtime.auth is None:
            return await JSONResponse({"detail": "Authenticated audit is not configured."}, 503)(scope, receive, private_send)
        try:
            auth = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
            scope.setdefault("state", {})["audit_principal"] = self.runtime.auth.authenticate(auth)
        except HTTPException as error:
            return await JSONResponse({"detail": error.detail}, error.status_code, headers=error.headers)(scope, receive, private_send)
        if self.active >= 4:
            return await JSONResponse({"detail": "Audit capacity is full. Retry later."}, 429)(scope, receive, private_send)
        self.active += 1
        try:
            if scope["method"] == "POST":
                maximum = 5 * 1024 * 1024 + 16384 if scope["path"].endswith("/analyze-document") else 512 * 1024
                chunks, size = [], 0
                try:
                    async with asyncio.timeout(15):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                return
                            chunk = message.get("body", b"")
                            size += len(chunk)
                            if size > maximum:
                                return await JSONResponse({"detail": "Audit request exceeds its size limit."}, 413)(scope, receive, private_send)
                            chunks.append(chunk)
                            if not message.get("more_body", False):
                                break
                except TimeoutError:
                    return await JSONResponse({"detail": "Audit upload timed out."}, 408)(scope, receive, private_send)
                body = b"".join(chunks)

                async def bounded_receive():
                    nonlocal body
                    if body is not None:
                        value, body = body, None
                        return {"type": "http.request", "body": value, "more_body": False}
                    return await receive()

                await self.app(scope, bounded_receive, private_send)
            else:
                await self.app(scope, receive, private_send)
        finally:
            self.active -= 1
