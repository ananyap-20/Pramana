"""Real outer HTTP boundary + real repositories, with local identity/Mongo doubles.

No live Firebase, Atlas, Bunny or confidential data is used in this module.
"""

import base64
from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
import secrets
import time
from uuid import uuid4

from docx import Document
from fastapi import HTTPException
from fastapi.testclient import TestClient
import mongomock
import pytest

from app.main import create_app
from app.services.identity import IdentityRuntime, FirebaseIdentity


ORIGIN = "https://pramana.test"


def claims(uid="alice", **extra):
    return {"uid": uid, "sub": uid, "email": "same@example.test", "email_verified": True,
            "auth_time": int(time.time()), "exp": int(time.time()) + 3600,
            "firebase": {"sign_in_provider": "password"}, **extra}


class Provider:
    def __init__(self):
        self.identities = {name: claims(name) for name in ("alice", "bob", "reader", "admin", "reviewer")}
        self.revoked = set()
        self.down = False

    def verify_token(self, token):
        if self.down:
            raise HTTPException(503, "Identity verification is unavailable.")
        uid = token.removeprefix("id-token-for-user-")
        if uid not in self.identities or uid in self.revoked:
            raise HTTPException(401, "Invalid credentials.")
        return self.identities[uid]

    def create_session(self, token, seconds):
        return "session-" + self.verify_token(token)["uid"]

    def verify_session(self, cookie):
        return self.verify_token("id-token-for-user-" + cookie.removeprefix("session-"))

    def revoke(self, uid):
        if self.down:
            raise HTTPException(503, "Provider unavailable.")
        self.revoked.add(uid)


@pytest.fixture
def protected_app(monkeypatch):
    for key in ("PRAMANA_AUDIT_IDENTITIES", "PRAMANA_REQUIRE_AUDIT", "PRAMANA_REQUIRE_BUNNY",
                "PRAMANA_BUNNY_STORAGE_ZONE", "PRAMANA_BUNNY_STORAGE_KEY", "FIREBASE_AUTH_EMULATOR_HOST"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRAMANA_FIREBASE_PROJECT_ID", "pramana-test")
    monkeypatch.setenv("CORS_ORIGINS", ORIGIN)
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    monkeypatch.setenv("MONGODB_DB", "pramana_identity_test")
    monkeypatch.setenv("PRAMANA_COOKIE_SECURE", "1")
    monkeypatch.setenv("PRAMANA_AUDIT_KEYS", json.dumps({"test": base64.b64encode(secrets.token_bytes(32)).decode()}))
    monkeypatch.setenv("PRAMANA_AUDIT_ACTIVE_KEY", "test")
    monkeypatch.setenv("PRAMANA_IDENTITY_MEMBERSHIPS", json.dumps([
        {"uid": uid, "organization_id": "org_team", "role": uid}
        for uid in ("reader", "reviewer", "admin")]))
    monkeypatch.setenv("PRAMANA_ENABLE_LOCAL_INTAKE", "1")
    database = mongomock.MongoClient(tz_aware=True)
    monkeypatch.setattr("app.repositories.audit_repository.MongoClient", lambda *a, **k: database)
    monkeypatch.setattr("app.repositories.mongodb_repository.MongoClient", lambda *a, **k: database)
    monkeypatch.setattr("app.audit_api.BunnyStorage.from_environment", lambda: None)
    async def pending(self, job):
        return None
    monkeypatch.setattr("app.services.extraction_store.ExtractionStore._extract", pending)
    app = create_app()
    provider = Provider()
    app.state.identity.provider = provider
    with TestClient(app, base_url=ORIGIN) as client:
        yield app, client, provider, database.pramana_identity_test


def csrf(client):
    return {"Origin": ORIGIN, "X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]}


def login(client, uid="alice"):
    result = client.post("/api/auth/session", json={"id_token": "id-token-for-user-" + uid}, headers=csrf(client))
    assert result.status_code == 204, result.text
    return result


def analyze(client, text="Our dashboard is guaranteed to eliminate all errors."):
    return client.post("/api/audit/reviews/analyze", json={"brand_id": "lumadesk", "draft_text": text},
                       headers={**csrf(client), "Idempotency-Key": str(uuid4())})


@pytest.mark.parametrize("path", ["/api/demo/config/lumadesk", "/api/reviews/history/lumadesk", "/api/intake/health",
    "/api/intake/guessed", "/api/intake/guessed/original", "/api/intake/guessed/pages/1/preview",
    "/api/audit/me", "/api/audit/reviews/guessed/snapshot", "/api/audit/reviews/guessed/original",
    "/api/audit/reviews/history/lumadesk", "/api/audit/analytics/lumadesk", "/docs", "/openapi.json"])
def test_all_private_get_surfaces_require_identity(protected_app, path):
    _, client, _, _ = protected_app
    result = client.get(path, headers={"Authorization": "Bearer " + "legacy-key" * 8})
    assert result.status_code == 401
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/api/reviews/analyze", "/api/reviews/analyze-document", "/api/reviews/guessed/decision",
    "/api/intake", "/api/intake/guessed/confirm", "/api/intake/guessed/cancel", "/api/intake/guessed/analyze",
    "/api/audit/reviews/analyze", "/api/audit/reviews/analyze-document", "/api/audit/intake/guessed/analyze",
    "/api/audit/reviews/guessed/decision", "/api/visual/analyze"])
def test_all_private_post_surfaces_require_identity_before_body_parsing(protected_app, path):
    _, client, _, _ = protected_app
    assert client.post(path, content=b"invalid confidential body", headers=csrf(client)).status_code == 401


def test_session_cookie_restore_csrf_logout_and_revocation(protected_app):
    app, client, provider, _ = protected_app
    for path in ("/health", "/ready", "/api/auth/config", "/api/auth/csrf"):
        assert client.get(path).status_code == 200
    assert client.get("/api/auth/session").status_code == 401
    result = login(client)
    cookie = result.headers["set-cookie"]
    assert cookie.startswith("__Host-pramana_session=")
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie
    assert client.get("/api/auth/session").json()["workspace"] == "personal"
    assert client.get("/api/demo/config/lumadesk").status_code == 200
    assert client.post("/api/auth/logout").status_code == 403
    headers = csrf(client)
    assert client.post("/api/auth/logout", headers={**headers, "Origin": "https://evil.test"}).status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert "alice" in provider.revoked
    assert client.get("/api/auth/session").status_code == 401
    client.cookies.set(app.state.identity.cookie_name, "session-alice")
    assert client.get("/api/demo/config/lumadesk").status_code == 401


def test_invalid_unverified_old_and_provider_failure_are_safe(protected_app):
    _, client, provider, _ = protected_app
    for uid, expected in [("missing", 401), ("unverified", 403), ("old", 401), ("anonymous", 403)]:
        provider.identities["unverified"] = claims("unverified", email_verified=False)
        provider.identities["old"] = claims("old", auth_time=int(time.time()) - 600)
        provider.identities["anonymous"] = claims("anonymous", firebase={"sign_in_provider": "anonymous"})
        # Token bounds stay realistic even for the local provider double.
        result = client.post("/api/auth/session", json={"id_token": "id-token-for-user-" + uid + ""}, headers=csrf(client))
        assert result.status_code == expected
    provider.down = True
    client.cookies.set("__Host-pramana_session", "session-alice")
    assert client.get("/api/demo/config/lumadesk").status_code == 503
    assert client.get("/api/reviews/history/lumadesk").status_code == 503
    result = client.post("/api/auth/session", json={"id_token": "secret-private-token-value", "role": "admin"}, headers=csrf(client))
    assert result.status_code == 422 and "secret-private" not in result.text


def test_personal_reviews_evidence_and_legacy_records_are_isolated(protected_app):
    app, client, _, database = protected_app
    # Never assign either old collection to a new UID, even with matching metadata.
    database.audit_reviews_v1.insert_one({"_id": "legacy", "organization_id": "org_team"})
    login(client)
    result = analyze(client)
    assert result.status_code == 200, result.text
    value = result.json()
    run_id = value["review_run_id"]
    document = database.identity_reviews_v1.find_one({"_id": run_id})
    assert "draft_text" not in document and b"dashboard" not in bytes(document["snapshot"]["ciphertext"])
    assert client.get(f"/api/audit/reviews/{run_id}/snapshot").json()["analysis"] == value
    assert client.get("/api/audit/reviews/legacy/snapshot").status_code == 404
    first_identity = client.get("/api/auth/session").json()
    login(client, "bob")
    second_identity = client.get("/api/auth/session").json()
    assert first_identity["organization_id"] != second_identity["organization_id"]  # same email, distinct UIDs
    for suffix in ("", "/snapshot"):
        assert client.get(f"/api/audit/reviews/{run_id}{suffix}").status_code == 404
    assert client.get("/api/audit/reviews/history/lumadesk").json()["records"] == []
    assert client.get("/api/audit/reviews/history/lumadesk?cursor=" + run_id).status_code == 404
    assert client.post(f"/api/audit/reviews/{run_id}/decision", json={"decision": "approved", "expected_revision": 0},
        headers={**csrf(client), "Idempotency-Key": str(uuid4())}).status_code == 404
    assert client.get("/api/reviews/history/lumadesk").status_code == 410
    assert client.post("/api/reviews/analyze", json={}, headers=csrf(client)).status_code == 410


def test_explicit_membership_roles_and_authorized_shared_reviews(protected_app):
    _, client, _, _ = protected_app
    login(client, "reviewer")
    run_id = analyze(client).json()["review_run_id"]
    login(client, "reader")
    assert client.get(f"/api/audit/reviews/{run_id}/snapshot").status_code == 200
    assert analyze(client).status_code == 403
    assert client.post(f"/api/audit/reviews/{run_id}/decision", json={"decision": "approved", "expected_revision": 0},
        headers={**csrf(client), "Idempotency-Key": str(uuid4())}).status_code == 403
    assert client.delete(f"/api/audit/reviews/{run_id}", headers=csrf(client)).status_code == 403
    login(client, "reviewer")
    response = client.post(f"/api/audit/reviews/{run_id}/decision", json={"decision": "revision", "expected_revision": 0},
        headers={**csrf(client), "Idempotency-Key": str(uuid4())})
    assert response.status_code == 200 and response.json()["revision"] == 1
    login(client, "admin")
    assert client.delete(f"/api/audit/reviews/{run_id}", headers=csrf(client)).status_code == 204
    assert client.get(f"/api/audit/reviews/{run_id}").status_code == 404


def test_extraction_needs_identity_owner_and_capability(protected_app):
    app, client, _, _ = protected_app
    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    login(client)
    response = client.post("/api/intake", data={"brand_id": "lumadesk"},
        files={"file": ("fictional.png", output.getvalue(), "image/png")}, headers=csrf(client))
    assert response.status_code == 202, response.text
    value = response.json()
    path = "/api/intake/" + value["extraction_id"]
    access = {"Authorization": "Bearer " + value["access_token"]}
    assert client.get(path, headers=access).status_code == 200
    assert client.get(path).status_code == 404
    login(client, "bob")
    for suffix in ("", "/original", "/versions/1", "/pages/1/preview"):
        assert client.get(path + suffix, headers=access).status_code == 404
    assert client.post(path + "/cancel", headers={**csrf(client), **access}).status_code == 404
    assert client.post("/api/audit/intake/" + value["extraction_id"] + "/analyze",
        json={"version": 1, "text_sha256": "a" * 64}, headers={**csrf(client), "Idempotency-Key": str(uuid4()),
        "X-Intake-Token": value["access_token"]}).status_code == 404
    client.cookies.delete(app.state.identity.cookie_name)
    assert client.get(path, headers=access).status_code == 401


def test_retained_originals_keep_parent_authorization(protected_app):
    app, client, _, database = protected_app
    from app.services.retained_files import RetainedFiles
    objects = {}
    class Storage:
        def check_ready(self): pass
        def request(self, method, key, content=None):
            if method == "PUT": objects[key] = content
            elif method == "GET": return objects[key]
            elif method == "DELETE": objects.pop(key, None)
    app.state.audit.files = RetainedFiles(app.state.audit.repository, Storage())
    document, output = Document(), BytesIO()
    document.add_paragraph("Fictional dashboard draft.")
    document.save(output)
    login(client)
    result = client.post("/api/audit/reviews/analyze-document", data={"brand_id": "lumadesk"},
        files={"file": ("draft.docx", output.getvalue())}, headers={**csrf(client), "Idempotency-Key": str(uuid4())})
    assert result.status_code == 200, result.text
    path = "/api/audit/reviews/" + result.json()["review_run_id"] + "/original"
    assert client.get(path).content == output.getvalue()
    assert database.identity_files_v1.count_documents({}) == 1
    assert database.audit_files_v1.count_documents({}) == 0
    login(client, "bob")
    assert client.get(path).status_code == 404


def test_cors_rate_limit_and_no_arbitrary_identity_claims(protected_app):
    _, client, provider, _ = protected_app
    assert client.options("/api/audit/me", headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "GET"}).status_code == 400
    result = client.options("/api/audit/me", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
    assert result.headers["access-control-allow-origin"] == ORIGIN
    assert result.headers["access-control-allow-credentials"] == "true"
    for _ in range(20):
        assert client.post("/api/auth/session", json={"id_token": "invalid-credential-value"}, headers=csrf(client)).status_code == 401
    assert client.post("/api/auth/session", json={"id_token": "invalid-credential-value"}, headers=csrf(client)).status_code == 429


def test_memberships_ignore_email_domains_and_client_roles(monkeypatch):
    monkeypatch.delenv("PRAMANA_FIREBASE_PROJECT_ID", raising=False)
    monkeypatch.delenv("PRAMANA_IDENTITY_MEMBERSHIPS", raising=False)
    runtime = IdentityRuntime((ORIGIN,))
    first = runtime.principal(claims("one", role="admin", organization_id="org_existing"))
    assert first.role == "reviewer" and first.organization_id.startswith("p_")
    assert runtime.principal(claims("two")).organization_id != first.organization_id
    assert runtime.principal(claims("one", email="admin@company.example")).organization_id == first.organization_id
    with pytest.raises(HTTPException) as error:
        runtime.require_provider()
    assert error.value.status_code == 503
    monkeypatch.setenv("PRAMANA_IDENTITY_MEMBERSHIPS", '[{"uid":"x","organization_id":"p_existing","role":"admin"}]')
    with pytest.raises(ValueError): IdentityRuntime((ORIGIN,))


def test_real_firebase_verifier_checks_signature_issuer_audience_expiry_and_rotation(monkeypatch):
    """Use real SDK + RSA signatures; replace only Google's certificate transport."""
    import firebase_admin
    from firebase_admin import _token_gen
    from google.auth import jwt
    from google.auth.crypt import RSASigner
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from types import SimpleNamespace

    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    app = firebase_admin.initialize_app(options={"projectId": "pramana-test"}, name="test-" + uuid4().hex)
    verifier = _token_gen.TokenVerifier(app)
    certificates = {}
    def signing_key(kid):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local-test")])
        now = datetime.now(UTC)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
        certificates[kid] = certificate.public_bytes(serialization.Encoding.PEM).decode()
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        return RSASigner.from_string(private, key_id=kid)
    first, rotated = signing_key("first"), signing_key("rotated")
    verifier.request = lambda *a, **k: SimpleNamespace(status=200, data=json.dumps(certificates).encode())
    captured = []
    def verify(cookie, app=None, check_revoked=False):
        captured.append(check_revoked)
        return verifier.verify_session_cookie(cookie)
    provider = FirebaseIdentity("pramana-test")
    monkeypatch.setattr(provider, "_sdk", lambda: SimpleNamespace(verify_session_cookie=verify))
    payload = {**claims(), "aud": "pramana-test", "iss": "https://session.firebase.google.com/pramana-test", "iat": int(time.time()) - 1}
    try:
        assert provider.verify_session(jwt.encode(first, payload).decode())["uid"] == "alice"
        assert captured == [True]
        for override in ({"aud": "other-project"}, {"iss": "https://attacker.test/pramana-test"},
                         {"exp": int(time.time()) - 30}, {"sub": ""}, {"iat": int(time.time()) + 300}):
            with pytest.raises(HTTPException) as error:
                provider.verify_session(jwt.encode(first, {**payload, **override}).decode())
            assert error.value.status_code == 401
        token = jwt.encode(first, payload).decode()
        header, body, signature = token.split(".")
        replacement = ("A" if signature[0] != "A" else "B") + signature[1:]
        with pytest.raises(HTTPException) as error:
            provider.verify_session(".".join((header, body, replacement)))
        assert error.value.status_code == 401
        assert provider.verify_session(jwt.encode(rotated, payload).decode())["uid"] == "alice"
        certificates.pop("first")
        with pytest.raises(HTTPException): provider.verify_session(token)
        from google.auth.exceptions import TransportError
        def unavailable(*a, **k): raise TransportError("sensitive transport detail")
        verifier.request = unavailable
        with pytest.raises(HTTPException) as error:
            provider.verify_session(jwt.encode(rotated, payload).decode())
        assert error.value.status_code == 503 and "sensitive" not in error.value.detail
    finally:
        firebase_admin.delete_app(app)


def test_reader_cannot_mutate_intake_visual_or_delete_other_workspaces(protected_app):
    _, client, _, _ = protected_app
    login(client, "reader")
    for path in ("/api/intake", "/api/intake/guessed/cancel", "/api/intake/guessed/confirm", "/api/visual/analyze"):
        assert client.post(path, content=b"unparsed", headers=csrf(client)).status_code == 403
    assert client.delete("/api/audit/reviews/guessed", headers=csrf(client)).status_code == 403


def test_logout_deletes_local_cookie_when_provider_is_unavailable(protected_app):
    _, client, provider, _ = protected_app
    login(client)
    provider.down = True
    result = client.post("/api/auth/logout", headers=csrf(client))
    assert result.status_code == 503
    assert "Max-Age=0" in result.headers["set-cookie"]
    assert "signed out" in result.json()["detail"]
    assert client.get("/api/auth/session").status_code == 401


def test_cleanup_preserves_expiry_for_legacy_files_without_exposing_them(protected_app):
    app, client, _, database = protected_app
    from app.services.retained_files import RetainedFiles
    deleted = []
    class Storage:
        def request(self, method, key, content=None): deleted.append((method, key))
    storage = Storage()
    app.state.audit.files = RetainedFiles(app.state.audit.repository, storage)
    app.state.audit.legacy_files = RetainedFiles(app.state.audit.repository, storage, collection_name="audit_files_v1")
    database.audit_files_v1.insert_one({"_id": "legacy", "object_key": "old-expired-file", "expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    database.identity_files_v1.insert_one({"_id": "current", "object_key": "new-retained-file", "expires_at": datetime.now(UTC) + timedelta(days=1)})
    app.state.audit.sweep_files()
    assert deleted == [("DELETE", "old-expired-file")]
    assert database.audit_files_v1.count_documents({}) == 0
    assert database.identity_files_v1.count_documents({}) == 1
    login(client)
    assert client.get("/api/audit/reviews/legacy/original").status_code == 404
