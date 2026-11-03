"""Public authentication entry points; passwords and OAuth stay with Firebase."""

import asyncio
import re
import secrets
import time
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.services.identity import request_actor


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=20, max_length=8192, repr=False)


class AuthRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid sign-in request.") from None
        return safe


def auth_router(runtime):
    router = APIRouter(prefix="/api/auth", tags=["Identity"], route_class=AuthRoute)

    @router.get("/config")
    def config():
        return {"configured": runtime.provider is not None, "project_id": runtime.project,
                "provider": "firebase", "session_seconds": runtime.seconds}

    @router.get("/csrf")
    def csrf(request: Request, response: Response):
        existing = request.cookies.get(runtime.csrf_name, "")
        token = existing if re.fullmatch(r"[A-Za-z0-9_-]{43}", existing) else secrets.token_urlsafe(32)
        response.set_cookie(runtime.csrf_name, token, httponly=True, secure=runtime.secure,
                            samesite="lax", path="/", max_age=3600)
        return {"csrf_token": token}

    @router.post("/session", status_code=204)
    def login(body: LoginBody):
        cookie = runtime.login(body.id_token)
        response = Response(status_code=204)
        response.set_cookie(runtime.cookie_name, cookie, httponly=True, secure=runtime.secure,
                            samesite="lax", path="/", max_age=runtime.seconds)
        return response

    @router.get("/session")
    def session(request: Request):
        claims, identity = runtime.session(request.cookies.get(runtime.cookie_name))
        return {"actor_id": identity.actor_id, "organization_id": identity.organization_id,
                "role": identity.role, "email": claims.get("email", ""), "expires_at": claims["exp"],
                "workspace": "personal" if identity.organization_id.startswith("p_") else "organization"}

    @router.post("/logout", status_code=204)
    def logout(request: Request):
        response = Response(status_code=204)
        response.delete_cookie(runtime.cookie_name, path="/", secure=runtime.secure, httponly=True, samesite="lax")
        try:
            claims, _ = runtime.session(request.cookies.get(runtime.cookie_name))
            runtime.require_provider().revoke(claims.get("uid") or claims["sub"])
        except HTTPException as error:
            if error.status_code != 401:
                response = JSONResponse({"detail": "This browser was signed out; remote session revocation is unavailable. Contact the operator to revoke other sessions."}, 503)
                response.delete_cookie(runtime.cookie_name, path="/", secure=runtime.secure, httponly=True, samesite="lax")
        return response

    return router


class IdentityMiddleware:
    """Authenticate before body parsing, deny legacy access, enforce origin + CSRF."""

    PUBLIC = {("GET", "/health"), ("GET", "/ready"), ("GET", "/api/auth/config"),
              ("GET", "/api/auth/csrf"), ("GET", "/api/auth/session"),
              ("POST", "/api/auth/session"), ("POST", "/api/auth/logout")}

    def __init__(self, app, runtime):
        self.app, self.runtime = app, runtime
        self.attempts = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        request = Request(scope)

        async def private_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([(b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")])
                identity = scope.get("state", {}).get("audit_principal")
                if identity:
                    message["headers"].append((b"x-pramana-context", f"{identity.actor_id}:{identity.organization_id}".encode()))
            await send(message)

        try:
            if method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin", "")
                csrf = request.headers.get("x-csrf-token", "")
                cookie = request.cookies.get(self.runtime.csrf_name, "")
                if origin not in self.runtime.origins or not 32 <= len(csrf) <= 128 or not secrets.compare_digest(csrf, cookie):
                    raise HTTPException(403, "The request origin or CSRF token is invalid. Reload and retry.")
            if path.startswith("/api/auth/") and method == "POST":
                now = time.monotonic()
                client = scope.get("client") or ("unknown", 0)
                host = client[0]
                count, deadline = self.attempts.get(host, (0, now + 60))
                if deadline <= now:
                    count, deadline = 0, now + 60
                self.attempts[host] = (count + 1, deadline)
                self.attempts.move_to_end(host)
                if len(self.attempts) > 2048:
                    self.attempts.popitem(last=False)
                if count >= 20:
                    raise HTTPException(429, "Too many authentication attempts. Retry in a minute.")
                # Bound the ID-token exchange before JSON parsing and validation.
                chunks, length = [], 0
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        length += len(chunk)
                        if length > 16384:
                            raise HTTPException(413, "Sign-in request is too large.")
                        chunks.append(chunk)
                        if not message.get("more_body", False):
                            break
                body = b"".join(chunks)
                original_receive = receive
                async def bounded_receive():
                    nonlocal body
                    if body is not None:
                        value, body = body, None
                        return {"type": "http.request", "body": value, "more_body": False}
                    return await original_receive()
                receive = bounded_receive
            if (method, path) in self.PUBLIC:
                return await self.app(scope, receive, private_send)
            claims, identity = await run_in_threadpool(self.runtime.session, request.cookies.get(self.runtime.cookie_name))
            if identity.role == "reader" and method not in {"GET", "HEAD", "OPTIONS"}:
                raise HTTPException(403, "Reviewer access is required for this action.")
            if path.startswith("/api/reviews") or (path.startswith("/api/intake/") and
                    (path.endswith("/analyze") or "/reviews/" in path)):
                raise HTTPException(410, "Legacy review access is disabled. Use your authenticated workspace.")
            state = scope.setdefault("state", {})
            state["audit_principal"] = identity
            token = request_actor.set(identity.actor_id)
            try:
                return await self.app(scope, receive, private_send)
            finally:
                request_actor.reset(token)
        except TimeoutError:
            return await JSONResponse({"detail": "Sign-in request timed out."}, 408)(scope, receive, private_send)
        except HTTPException as error:
            return await JSONResponse({"detail": error.detail}, error.status_code)(scope, receive, private_send)
