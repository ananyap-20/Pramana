"""PDF acceptance through the real identity/CSRF middleware and extraction worker.

Only Firebase verification and MongoDB are replaced with local test doubles.
"""

import base64
import json
import os
from pathlib import Path
import secrets
import time

from fastapi import HTTPException
from fastapi.testclient import TestClient
import mongomock
import pytest

from app.main import create_app
from backend.tests.intake_fixtures import pdf_bytes


@pytest.fixture
def signed_intake(monkeypatch):
    monkeypatch.setenv("PRAMANA_FIREBASE_PROJECT_ID", "pramana-test")
    monkeypatch.setenv("PRAMANA_COOKIE_SECURE", "0")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost/pramana_fixture")
    monkeypatch.setenv("PRAMANA_AUDIT_KEYS", json.dumps({"fixture": base64.b64encode(secrets.token_bytes(32)).decode()}))
    monkeypatch.setenv("PRAMANA_AUDIT_ACTIVE_KEY", "fixture")
    monkeypatch.setenv("PRAMANA_ENABLE_LOCAL_INTAKE", "1")
    monkeypatch.delenv("PRAMANA_AUDIT_IDENTITIES", raising=False)
    monkeypatch.setattr("app.repositories.audit_repository.MongoClient", mongomock.MongoClient)
    monkeypatch.setattr("app.repositories.mongodb_repository.MongoClient", mongomock.MongoClient)
    local = Path("tmp/ocr-runtime/tesseract/tesseract.exe").resolve()
    if local.is_file():
        monkeypatch.setenv("TESSERACT_CMD", str(local))
        monkeypatch.setenv("TESSDATA_DIR", str(local.parent / "tessdata"))

    class Provider:
        def claims(self, uid):
            return {"uid": uid, "email": "fixture@example.test", "email_verified": True,
                    "auth_time": time.time(), "exp": time.time() + 3600,
                    "firebase": {"sign_in_provider": "password"}}

        def verify_token(self, token):
            return self.claims("fixture-user")

        def create_session(self, token, seconds):
            return "fixture-session"

        def verify_session(self, cookie):
            if cookie not in {"fixture-session", "other-session"}:
                raise HTTPException(401, "Invalid fixture session.")
            return self.claims("other-user" if cookie == "other-session" else "fixture-user")

    app = create_app()
    app.state.identity.provider = Provider()
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        headers = {"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": csrf}
        login = client.post("/api/auth/session", json={"id_token": "fixture-token-" * 3}, headers=headers)
        assert login.status_code == 204, login.text
        yield client, headers


@pytest.mark.parametrize("kind", ["text", "scan", "mixed"])
def test_signed_pdf_upload_confirm_analyze_and_decide(signed_intake, kind):
    client, headers = signed_intake
    health = client.get("/api/intake/health").json()
    assert health["enabled"]
    if kind != "text" and not health["ocr_ready"]:
        if os.getenv("REQUIRE_REAL_OCR") == "1":
            pytest.fail("OCR runtime is required for this acceptance run.")
        pytest.skip("Tesseract English runtime is unavailable.")
    content = pdf_bytes(("text", "scan", "hybrid") if kind == "mixed" else (kind,))
    assert client.post("/api/intake", data={"brand_id": "lumadesk"},
        files={"file": ("fixture.pdf", content, "application/pdf")}).status_code == 403
    response = client.post("/api/intake", headers=headers, data={"brand_id": "lumadesk"},
        files={"file": ("fixture.pdf", content, "application/pdf")})
    assert response.status_code == 202, response.text
    created = response.json()
    path = f"/api/intake/{created['extraction_id']}"
    access = {**headers, "Authorization": f"Bearer {created['access_token']}"}
    deadline = time.monotonic() + 75
    while True:
        status = client.get(path, headers=access)
        assert status.status_code == 200, status.text
        job = status.json()
        if job["state"] not in {"queued", "processing"}:
            break
        assert time.monotonic() < deadline, "Extraction exceeded acceptance deadline."
        time.sleep(.05)
    assert job["state"] == "needs_confirmation", job
    assert "dashboard" in job["current"]["text"].lower()
    assert client.get(path + "/pages/1/preview", headers=access).content.startswith(b"\x89PNG")
    confirmed = client.post(path + "/confirm", headers=access, json={
        "version": job["current"]["version"], "text_sha256": job["current"]["text_sha256"],
        "page_texts": [p["text"] for p in job["current"]["pages"]], "confirm_transcription": True})
    assert confirmed.status_code == 200, confirmed.text
    ready = confirmed.json()
    assert ready["confirmation"]["actor_kind"] == "authenticated_user"
    analysis_path = f"/api/audit/intake/{created['extraction_id']}/analyze"
    analysis_headers = {**headers, "X-Intake-Token": created["access_token"], "Idempotency-Key": secrets.token_hex(16)}
    response = client.post(analysis_path, headers=analysis_headers, json={
        "version": ready["current"]["version"], "text_sha256": ready["current"]["text_sha256"]})
    assert response.status_code == 200, response.text
    review = response.json()
    assert review["draft_text"] == ready["current"]["text"]
    assert review["persistence"] == "mongodb_encrypted_audit"
    decision = client.post(f"/api/audit/reviews/{review['review_run_id']}/decision",
        headers={**headers, "Idempotency-Key": secrets.token_hex(16)},
        json={"decision": "revision", "expected_revision": 0})
    assert decision.status_code == 200, decision.text
    client.cookies.set("pramana_local_session", "other-session", domain="127.0.0.1", path="/")
    assert client.get(path, headers=access).status_code == 404
