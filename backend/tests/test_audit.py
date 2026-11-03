"""Audit security and real MongoDB acceptance checks on disposable local databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

from docx import Document
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo import MongoClient
import pytest

from app.main import create_app
from app.audit_models import AuditProblem
from app.repositories.audit_repository import AuditRepository
from app.services.audit_security import AuditAuth, AuditPrincipal, SnapshotCipher


def encryption():
    return SnapshotCipher(json.dumps({"test": base64.b64encode(secrets.token_bytes(32)).decode()}), "test")


def test_private_original_survives_restart_and_rejects_other_organization(audit_environment, monkeypatch):
    tokens, database, _ = audit_environment
    objects = {}

    class Storage:
        def check_ready(self):
            pass

        def request(self, method, key, content=None):
            if method == "PUT":
                objects[key] = content
            elif method == "GET":
                return objects[key]
            elif method == "DELETE":
                objects.pop(key, None)

    monkeypatch.setattr("app.audit_api.BunnyStorage.from_environment", lambda: Storage())
    document = Document()
    document.add_paragraph("Fictional original: our dashboard is guaranteed to eliminate all errors.")
    buffer = BytesIO()
    document.save(buffer)
    content = buffer.getvalue()
    key = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/api/audit/reviews/analyze-document", headers=headers(tokens, key=key),
            data={"brand_id": "lumadesk"}, files={"file": ("test.docx", content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert response.status_code == 200, response.text
        run_id = response.json()["review_run_id"]
        assert len(objects) == 1 and next(iter(objects.values())) != content
        assert client.post("/api/audit/reviews/analyze-document", headers=headers(tokens, key=key),
            data={"brand_id": "lumadesk"}, files={"file": ("test.docx", content)}).status_code == 200
        assert len(objects) == 1
    with TestClient(create_app()) as client:
        path = f"/api/audit/reviews/{run_id}/original"
        restored = client.get(path, headers=headers(tokens))
        assert restored.status_code == 200 and restored.content == content
        assert restored.headers["cache-control"] == "no-store"
        assert client.get(path).status_code == 401
        assert client.get(path, headers=headers(tokens, "other")).status_code == 404
        assert client.delete(f"/api/audit/reviews/{run_id}", headers=headers(tokens, "admin")).status_code == 204
        assert not objects
        assert database.audit_files_v1.count_documents({}) == 0


def test_authenticated_encryption_and_key_rotation():
    cipher = encryption()
    envelope = cipher.encrypt("org-a", "run-a", b"private draft")
    assert cipher.decrypt("org-a", "run-a", envelope) == b"private draft"
    assert envelope != cipher.encrypt("org-a", "run-a", b"private draft")
    for organization, run_id in [("org-b", "run-a"), ("org-a", "run-b")]:
        with pytest.raises(AuditProblem) as error:
            cipher.decrypt(organization, run_id, envelope)
        assert error.value.status == 503
    modified = {**envelope, "ciphertext": bytes(envelope["ciphertext"][:-1]) + bytes([envelope["ciphertext"][-1] ^ 1])}
    with pytest.raises(AuditProblem):
        cipher.decrypt("org-a", "run-a", modified)
    keys = {"test": base64.b64encode(cipher.keys["test"]).decode(), "next": base64.b64encode(secrets.token_bytes(32)).decode()}
    rotated = SnapshotCipher(json.dumps(keys), "next")
    assert rotated.decrypt("org-a", "run-a", envelope) == b"private draft"
    assert rotated.encrypt("org-a", "run-b", b"new")["key_id"] == "next"


def test_identity_configuration_and_invalid_credentials():
    token = secrets.token_urlsafe(32)
    identities = [{"token_sha256": hashlib.sha256(token.encode()).hexdigest(), "actor_id": "user", "organization_id": "org", "role": "reviewer"}]
    auth = AuditAuth(json.dumps(identities))
    assert auth.authenticate("Bearer " + token) == AuditPrincipal("user", "org", "reviewer")
    for invalid in [None, "Bearer short", "Basic " + token, "Bearer " + secrets.token_urlsafe(32)]:
        with pytest.raises(HTTPException) as error:
            auth.authenticate(invalid)
        assert error.value.status_code == 401
    with pytest.raises(ValueError):
        AuditAuth(json.dumps(identities * 2))
    for invalid in ["{}", "[]", "secret-not-json"]:
        with pytest.raises(ValueError, match="Invalid audit"):
            AuditAuth(invalid)


def test_audit_is_fail_closed_without_configuration(monkeypatch):
    for key in ("PRAMANA_AUDIT_IDENTITIES", "PRAMANA_AUDIT_KEYS", "PRAMANA_AUDIT_ACTIVE_KEY", "MONGODB_URI"):
        monkeypatch.delenv(key, raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/api/audit/me").status_code == 503
    monkeypatch.setenv("PRAMANA_AUDIT_IDENTITIES", "[]")
    with pytest.raises(ValueError, match="requires MongoDB"):
        create_app()


def test_credential_generator_preserves_existing_keys(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "create_audit_credentials.py"
    output = tmp_path / ".env.audit"
    command = [sys.executable, str(script), "--actor", "user1", "--organization", "org1", "--output", str(output)]
    created = subprocess.run(command, capture_output=True, timeout=10)
    assert created.returncode == 0
    content = output.read_bytes()
    token = output.with_name(output.name + ".access-key").read_text().strip()
    assert len(token) >= 32 and token.encode() not in content and token.encode() not in created.stdout
    repeated = subprocess.run(command, capture_output=True, timeout=10)
    assert repeated.returncode != 0 and output.read_bytes() == content


@pytest.fixture
def audit_environment(monkeypatch):
    uri = os.getenv("PRAMANA_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set PRAMANA_TEST_MONGODB_URI to a disposable local MongoDB for acceptance tests.")
    from urllib.parse import urlparse
    if urlparse(uri).hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Integration tests require an explicitly local database.")
    database = "pramana_audit_test_" + uuid4().hex
    tokens = {role: secrets.token_urlsafe(32) for role in ("admin", "reviewer", "reader", "other")}
    identities = [{"token_sha256": hashlib.sha256(token.encode()).hexdigest(), "actor_id": role,
                   "organization_id": "other-org" if role == "other" else "test-org",
                   "role": "reviewer" if role == "other" else role} for role, token in tokens.items()]
    monkeypatch.setenv("MONGODB_URI", uri)
    monkeypatch.setenv("MONGODB_DB", database)
    monkeypatch.setenv("PRAMANA_AUDIT_IDENTITIES", json.dumps(identities))
    monkeypatch.setenv("PRAMANA_AUDIT_KEYS", json.dumps({"test": base64.b64encode(secrets.token_bytes(32)).decode()}))
    monkeypatch.setenv("PRAMANA_AUDIT_ACTIVE_KEY", "test")
    monkeypatch.setenv("PRAMANA_AUDIT_RETENTION_DAYS", "30")
    client = MongoClient(uri, tz_aware=True)
    try:
        client.admin.command("ping")
        yield tokens, client[database], uri
    finally:
        # Exact randomly created test namespace only, never configured application data.
        client.drop_database(database)
        client.close()


def headers(tokens, role="reviewer", key=None):
    return {"Authorization": "Bearer " + tokens[role], **({"Idempotency-Key": key} if key else {})}


def analyze(client, tokens, text="Our dashboard is guaranteed to eliminate all errors.", role="reviewer", key=None):
    return client.post("/api/audit/reviews/analyze", json={"brand_id": "lumadesk", "draft_text": text},
                       headers=headers(tokens, role, key or str(uuid4())))


def decide(client, tokens, run_id, decision="revision", revision=0, key=None, role="reviewer"):
    return client.post(f"/api/audit/reviews/{run_id}/decision", json={"decision": decision, "expected_revision": revision},
                       headers=headers(tokens, role, key or str(uuid4())))


def test_restart_evidence_and_decisions_survive(audit_environment):
    tokens, database, _ = audit_environment
    key = str(uuid4())
    with TestClient(create_app()) as client:
        result = analyze(client, tokens, key=key)
        assert result.status_code == 200, result.text
        analysis = result.json()
        run_id = analysis["review_run_id"]
        event = decide(client, tokens, run_id).json()
        assert event["revision"] == 1 and event["actor_id"] == "reviewer"
        document = database.audit_reviews_v1.find_one({"_id": run_id})
        assert b"dashboard" not in bytes(document["snapshot"]["ciphertext"])
        assert "draft_text" not in document and "findings" not in document
    # Fresh application and fresh database clients, with no process-local review state.
    with TestClient(create_app()) as restarted:
        response = restarted.get(f"/api/audit/reviews/{run_id}/snapshot", headers=headers(tokens))
        assert response.status_code == 200
        assert response.json()["analysis"] == analysis
        assert response.json()["configuration"]["sources"]
        summary = restarted.get(f"/api/audit/reviews/{run_id}", headers=headers(tokens)).json()
        assert summary["decision_history"][0]["decision_id"] == event["decision_id"]
        assert analyze(restarted, tokens, key=key).json() == analysis
        assert restarted.get('/api/reviews/history/lumadesk').json() == []
        assert restarted.post(f'/api/reviews/{run_id}/decision', json={"decision": "approved"}).status_code == 404


def test_authorization_roles_and_organization_separation(audit_environment):
    tokens, _, _ = audit_environment
    with TestClient(create_app()) as client:
        contract = client.get('/openapi.json').json()["paths"]["/api/audit/reviews/analyze"]["post"]
        assert contract["security"] == [{"APIKeyCookie": []}]
        assert contract["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith('/AuditError')
        assert client.get('/api/audit/me').status_code == 401
        assert analyze(client, tokens, role="reader").status_code == 403
        run_id = analyze(client, tokens).json()["review_run_id"]
        for suffix in ["", "/snapshot"]:
            assert client.get(f'/api/audit/reviews/{run_id}{suffix}', headers=headers(tokens, "other")).status_code == 404
        assert decide(client, tokens, run_id, role="other").status_code == 404
        assert decide(client, tokens, run_id, role="reader").status_code == 403
        assert client.get('/api/audit/reviews/history/lumadesk', headers=headers(tokens, "other")).json()["records"] == []
        assert client.get('/api/audit/analytics/lumadesk', headers=headers(tokens, "other")).json()["total_runs"] == 0
        assert client.delete(f'/api/audit/reviews/{run_id}', headers=headers(tokens, "reviewer")).status_code == 403
        assert client.delete(f'/api/audit/reviews/{run_id}', headers=headers(tokens, "other")).status_code == 403
        assert client.post('/api/audit/reviews/analyze', json={"brand_id": "lumadesk", "draft_text": "Text", "organization_id": "other-org"}, headers=headers(tokens, key=str(uuid4()))).status_code == 422


def test_idempotency_and_concurrent_decisions(audit_environment):
    tokens, database, _ = audit_environment
    with TestClient(create_app()) as client:
        key = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            analyses = list(pool.map(lambda _: analyze(client, tokens, key=key), range(2)))
        assert [r.status_code for r in analyses] == [200, 200]
        run_id = analyses[0].json()["review_run_id"]
        assert analyses[1].json()["review_run_id"] == run_id
        assert database.audit_reviews_v1.count_documents({}) == 1
        assert analyze(client, tokens, text="Changed", key=key).status_code == 409
        decision_key = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: decide(client, tokens, run_id, key=decision_key), range(2)))
        assert all(r.status_code == 200 for r in responses)
        assert responses[0].json() == responses[1].json()
        assert decide(client, tokens, run_id, decision="approved", key=decision_key).status_code == 409
        with ThreadPoolExecutor(max_workers=2) as pool:
            competing = list(pool.map(lambda item: decide(client, tokens, run_id, decision=item[0], revision=1, role=item[1]), [("approved", "reviewer"), ("rejected", "admin")]))
        assert sorted(r.status_code for r in competing) == [200, 409]
        record = database.audit_reviews_v1.find_one({"_id": run_id})
        assert record["revision"] == len(record["events"]) == 2
        assert [e["revision"] for e in record["events"]] == [1, 2]


def test_analytics_reconciles_full_cohort_not_history_page(audit_environment):
    tokens, database, _ = audit_environment
    with TestClient(create_app()) as client:
        analyses = [analyze(client, tokens, text=t).json() for t in ["dashboard", "Guaranteed to eliminate all errors.", "Hello", "Hello again"]]
        for i, decision in [(0, "revision"), (1, "rejected"), (2, "approved")]:
            assert decide(client, tokens, analyses[i]["review_run_id"], decision=decision).status_code == 200
        assert decide(client, tokens, analyses[0]["review_run_id"], decision="approved", revision=1).status_code == 200
        now = datetime.now(UTC)
        # Different day, still within selected cohort, plus an out-of-period run.
        database.audit_reviews_v1.update_one({"_id": analyses[3]["review_run_id"]}, {"$set": {"evaluated_at": now - timedelta(days=2)}})
        analyze(client, tokens, role="other")
        analytics = client.get('/api/audit/analytics/lumadesk', headers=headers(tokens)).json()
        assert analytics["total_runs"] == 4
        assert analytics["total_findings"] == sum(len(a["findings"]) for a in analyses)
        assert analytics["decision_events"] == 4
        assert analytics["outcomes"] == {"approved": 2, "rejected": 1, "revision": 0, "pending": 1}
        assert sum(analytics["categories"].values()) == analytics["total_findings"]
        assert sum(r["count"] for r in analytics["repeated_rules"]) == analytics["total_findings"]
        assert sum(d["runs"] for d in analytics["daily"]) == 4
        page = client.get('/api/audit/reviews/history/lumadesk?limit=2', headers=headers(tokens)).json()
        assert len(page["records"]) == 2 and page["next_cursor"]
        second = client.get('/api/audit/reviews/history/lumadesk?limit=2&cursor=' + page["next_cursor"], headers=headers(tokens)).json()
        ids = [r["review_run_id"] for r in page["records"] + second["records"]]
        assert len(set(ids)) == 4 and second["next_cursor"] is None
        recent = client.get('/api/audit/analytics/lumadesk', params={"start": (now - timedelta(days=1)).isoformat(), "end": now.isoformat()}, headers=headers(tokens)).json()
        assert recent["total_runs"] == 3


def test_retention_deletion_limits_and_safe_errors(audit_environment):
    tokens, database, _ = audit_environment
    with TestClient(create_app()) as client:
        run_id = analyze(client, tokens).json()["review_run_id"]
        database.audit_reviews_v1.update_one({"_id": run_id}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
        assert client.get(f'/api/audit/reviews/{run_id}', headers=headers(tokens)).status_code == 404
        assert client.get(f'/api/audit/reviews/{run_id}/snapshot', headers=headers(tokens)).status_code == 404
        assert decide(client, tokens, run_id).status_code == 404
        assert client.get('/api/audit/analytics/lumadesk', headers=headers(tokens)).json()["total_runs"] == 0
        run_id = analyze(client, tokens).json()["review_run_id"]
        assert client.delete(f'/api/audit/reviews/{run_id}', headers=headers(tokens, "admin")).status_code == 204
        assert client.delete(f'/api/audit/reviews/{run_id}', headers=headers(tokens, "admin")).status_code == 204
        assert client.get(f'/api/audit/reviews/{run_id}', headers=headers(tokens)).status_code == 404
        assert client.post('/api/audit/reviews/analyze', content=b'x' * (512 * 1024 + 1), headers=headers(tokens)).status_code == 413
        error = client.post('/api/audit/reviews/analyze', content=b'PRIVATE invalid JSON', headers=headers(tokens))
        assert error.status_code == 422 and 'PRIVATE' not in error.text
        assert client.get('/api/audit/analytics/lumadesk?start=2026-01-01', headers=headers(tokens)).status_code == 422
        assert client.get('/api/audit/me', headers=headers(tokens)).headers["cache-control"] == "no-store"


def test_docx_durable_snapshot(audit_environment):
    tokens, _, _ = audit_environment
    document = Document()
    document.add_paragraph("Fictional dashboard.")
    stream = BytesIO()
    document.save(stream)
    with TestClient(create_app()) as client:
        result = client.post('/api/audit/reviews/analyze-document', data={"brand_id": "lumadesk"},
            files={"file": ("draft.docx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}, headers=headers(tokens, key=str(uuid4())))
        assert result.status_code == 200, result.text
        assert result.json()["input_type"] == "docx"
        assert result.json()["persistence"] == "mongodb_encrypted_audit"


def test_confirmed_pdf_review_survives_expired_extraction(audit_environment, monkeypatch):
    from backend.tests.test_pdf_image_intake import upload, wait_extracted, confirmation, reference
    tokens, _, _ = audit_environment
    monkeypatch.setenv("PRAMANA_ENABLE_LOCAL_INTAKE", "1")
    with TestClient(create_app()) as client:
        job, upload_headers = upload(client)
        base = f"/api/intake/{job['extraction_id']}"
        extracted = wait_extracted(client, job, upload_headers)
        ready = client.post(base + '/confirm', json=confirmation(extracted), headers=upload_headers).json()
        audit_headers = {**headers(tokens, key=str(uuid4())), "X-Intake-Token": job["access_token"]}
        saved = client.post('/api/audit/intake/' + job['extraction_id'] + '/analyze', json=reference(ready), headers=audit_headers)
        assert saved.status_code == 200, saved.text
        analysis = saved.json()
        assert analysis["document_provenance"]["text_sha256"] == ready["current"]["text_sha256"]
        assert decide(client, tokens, analysis["review_run_id"]).status_code == 200
    with TestClient(create_app()) as restarted:
        # Upload state is gone, but saved evaluated evidence and its human decision are still available.
        assert restarted.get(base, headers=upload_headers).status_code == 404
        snapshot = restarted.get(f'/api/audit/reviews/{analysis["review_run_id"]}/snapshot', headers=headers(tokens))
        assert snapshot.status_code == 200 and snapshot.json()["analysis"] == analysis
        assert restarted.get(f'/api/audit/reviews/{analysis["review_run_id"]}', headers=headers(tokens)).json()["revision"] == 1


def test_database_process_restart_preserves_journaled_audit(audit_environment):
    container = os.getenv("PRAMANA_TEST_MONGO_CONTAINER")
    if not container:
        pytest.skip("Set PRAMANA_TEST_MONGO_CONTAINER for actual database restart verification.")
    tokens, _, uri = audit_environment
    with TestClient(create_app()) as client:
        analysis = analyze(client, tokens).json()
        event = decide(client, tokens, analysis["review_run_id"]).json()
    result = subprocess.run(["docker.exe", "restart", container], capture_output=True, timeout=45)
    assert result.returncode == 0, result.stderr.decode()
    connection = MongoClient(uri, serverSelectionTimeoutMS=20000)
    try:
        connection.admin.command("ping")
    finally:
        connection.close()
    with TestClient(create_app()) as restarted:
        record = restarted.get(f'/api/audit/reviews/{analysis["review_run_id"]}', headers=headers(tokens)).json()
        assert record["decision_history"][0]["decision_id"] == event["decision_id"]
        assert restarted.get(f'/api/audit/reviews/{analysis["review_run_id"]}/snapshot', headers=headers(tokens)).json()["analysis"] == analysis


def test_event_cap_and_evidence_integrity(audit_environment):
    tokens, database, _ = audit_environment
    with TestClient(create_app()) as client:
        run_id = analyze(client, tokens).json()["review_run_id"]
        for revision in range(100):
            assert decide(client, tokens, run_id, revision=revision).status_code == 200
        assert decide(client, tokens, run_id, revision=100).status_code == 409
        document = database.audit_reviews_v1.find_one({"_id": run_id})
        assert len(document["events"]) == document["revision"] == 100
        database.audit_reviews_v1.update_one({"_id": run_id}, {"$set": {"draft_sha256": "tampered"}})
        assert client.get(f'/api/audit/reviews/{run_id}/snapshot', headers=headers(tokens)).status_code == 503


def test_backup_restore_real_database(audit_environment):
    container = os.getenv("PRAMANA_TEST_MONGO_CONTAINER")
    if not container:
        pytest.skip("Set PRAMANA_TEST_MONGO_CONTAINER for real mongodump/mongorestore verification.")
    tokens, database, uri = audit_environment
    restored_name = database.name + "_restore"
    client = MongoClient(uri)
    archive = "/tmp/" + uuid4().hex + ".archive"
    try:
        with TestClient(create_app()) as app_client:
            analysis = analyze(app_client, tokens).json()
            event = decide(app_client, tokens, analysis["review_run_id"]).json()
        commands = [
            ["docker.exe", "exec", container, "mongodump", "--db", database.name, "--archive=" + archive],
            ["docker.exe", "exec", container, "mongorestore", "--archive=" + archive,
             "--nsFrom=" + database.name + ".*", "--nsTo=" + restored_name + ".*"],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, timeout=60)
            assert result.returncode == 0, result.stderr.decode()
        cipher = SnapshotCipher(os.environ["PRAMANA_AUDIT_KEYS"], "test")
        restored = AuditRepository(uri, restored_name, cipher)
        try:
            restored.start()
            identity = AuditPrincipal("reviewer", "test-org", "reviewer")
            record = restored.get(identity, analysis["review_run_id"], with_snapshot=True)
            assert restored.snapshot(identity, record).analysis.model_dump(mode="json") == analysis
            assert restored.summary(record).decision_history[0].decision_id == event["decision_id"]
            indexes = restored.collection.index_information()
            assert any(index.get("expireAfterSeconds") == 0 for index in indexes.values())
            assert any(index.get("unique") for index in indexes.values())
        finally:
            restored.close()
    finally:
        client.drop_database(restored_name)
        client.close()
        subprocess.run(["docker.exe", "exec", container, "rm", "-f", archive], capture_output=True, timeout=10)
