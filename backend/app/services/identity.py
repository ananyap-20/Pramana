"""Firebase identity verification and explicit, server-owned workspace membership."""

from contextvars import ContextVar
from datetime import timedelta
import hashlib
import json
import os
import re
import time

from fastapi import HTTPException

from app.services.audit_security import AuditPrincipal


request_actor: ContextVar[str | None] = ContextVar("pramana_request_actor", default=None)


class FirebaseIdentity:
    """The Admin SDK owns JWT verification, certificate caching and key rotation."""

    def __init__(self, project: str):
        self.project = project
        self.app = None

    def _sdk(self):
        import firebase_admin
        from firebase_admin import auth
        if self.app is None:
            name = "pramana-" + self.project
            try:
                self.app = firebase_admin.get_app(name)
            except ValueError:
                self.app = firebase_admin.initialize_app(options={"projectId": self.project, "httpTimeout": 5}, name=name)
        return auth

    def _call(self, operation, *args, **kwargs):
        try:
            auth = self._sdk()
            return getattr(auth, operation)(*args, app=self.app, **kwargs)
        except HTTPException:
            raise
        except Exception as error:
            # Firebase's invalid/expired/revoked tokens are authorization failures;
            # certificate fetch, ADC, transport and provider failures fail closed.
            from firebase_admin import auth
            if isinstance(error, (auth.InvalidIdTokenError, auth.InvalidSessionCookieError,
                                  auth.RevokedIdTokenError, auth.RevokedSessionCookieError,
                                  auth.UserDisabledError, auth.UserNotFoundError)):
                raise HTTPException(401, "Your session is invalid or expired. Sign in again.") from None
            raise HTTPException(503, "Identity verification is unavailable. Retry later.") from None

    def verify_session(self, cookie: str):
        return self._call("verify_session_cookie", cookie, check_revoked=True)

    def verify_token(self, token: str):
        return self._call("verify_id_token", token, check_revoked=True)

    def create_session(self, token: str, seconds: int):
        return self._call("create_session_cookie", token, expires_in=timedelta(seconds=seconds))

    def revoke(self, uid: str):
        self._call("revoke_refresh_tokens", uid)


class IdentityRuntime:
    def __init__(self, origins):
        self.project = os.getenv("PRAMANA_FIREBASE_PROJECT_ID", "").strip()
        if self.project and not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", self.project):
            raise ValueError("Invalid Firebase project ID.")
        if os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
            raise ValueError("The authentication emulator is not allowed in this application runtime.")
        self.provider = FirebaseIdentity(self.project) if self.project else None
        self.origins = origins
        self.secure = os.getenv("PRAMANA_COOKIE_SECURE", "1") != "0"
        if not self.secure and any(not re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:[0-9]+)?", o) for o in origins):
            raise ValueError("Insecure cookies are permitted only with loopback HTTP origins.")
        self.cookie_name = "__Host-pramana_session" if self.secure else "pramana_local_session"
        self.csrf_name = "__Host-pramana_csrf" if self.secure else "pramana_local_csrf"
        self.seconds = 5 * 24 * 60 * 60
        try:
            mappings = json.loads(os.getenv("PRAMANA_IDENTITY_MEMBERSHIPS", "[]"))
            if not isinstance(mappings, list) or len(mappings) > 1000:
                raise ValueError()
            self.memberships = {}
            for item in mappings:
                if set(item) != {"uid", "organization_id", "role"}:
                    raise ValueError()
                uid, org, role = item["uid"], item["organization_id"], item["role"]
                if (not isinstance(uid, str) or not 1 <= len(uid) <= 128 or uid in self.memberships or
                        not re.fullmatch(r"org_[A-Za-z0-9_-]{1,59}", org) or role not in {"reader", "reviewer", "admin"}):
                    raise ValueError()
                self.memberships[uid] = (org, role)
        except (ValueError, TypeError, KeyError):
            raise ValueError("Invalid identity membership configuration.") from None

    def require_provider(self):
        if self.provider is None:
            raise HTTPException(503, "Sign-in is not configured. Contact the operator.")
        return self.provider

    def principal(self, claims):
        uid = claims.get("uid") or claims.get("sub")
        firebase = claims.get("firebase")
        if not isinstance(firebase, dict):
            raise HTTPException(403, "A supported sign-in method is required.")
        provider = firebase.get("sign_in_provider")
        if (not isinstance(uid, str) or not 1 <= len(uid) <= 128 or claims.get("email_verified") is not True or
                provider not in {"password", "google.com", "github.com"} or firebase.get("tenant")):
            raise HTTPException(403, "A verified email and a supported sign-in method are required.")
        actor = "u_" + hashlib.sha256((self.project + ":" + uid).encode()).hexdigest()[:60]
        organization, role = self.memberships.get(uid, ("p_" + actor[2:], "reviewer"))
        return AuditPrincipal(actor, organization, role)

    def session(self, cookie):
        if not cookie or len(cookie) > 8192:
            raise HTTPException(401, "Sign in to continue.")
        claims = self.require_provider().verify_session(cookie)
        return claims, self.principal(claims)

    def login(self, token):
        provider = self.require_provider()
        claims = provider.verify_token(token)
        self.principal(claims)
        authenticated = claims.get("auth_time", 0)
        if not isinstance(authenticated, (int, float)) or not -30 <= time.time() - authenticated <= 300:
            raise HTTPException(401, "Sign in again before starting a session.")
        return provider.create_session(token, self.seconds)
