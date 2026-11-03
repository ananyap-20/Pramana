"""Transport and retention failure contracts; no provider credentials used."""

from datetime import UTC, datetime, timedelta
import base64
import json
from unittest.mock import MagicMock
import urllib.error

import pytest

from app.audit_models import AuditProblem
from app.config import get_settings
from app.services.audit_security import AuditPrincipal, SnapshotCipher
from app.services.bunny_storage import BunnyStorage, MAX_OBJECT_BYTES, NoRedirect
from app.services.retained_files import RetainedFiles


def test_storage_configuration_fails_closed(monkeypatch):
    for name in ("BUNNY_STORAGE_HOST", "BUNNY_STORAGE_ZONE", "BUNNY_STORAGE_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    assert BunnyStorage.from_environment() is None
    monkeypatch.setenv("BUNNY_STORAGE_ZONE", "zone")
    with pytest.raises(ValueError):
        BunnyStorage.from_environment()
    for host in ("https://storage.bunnycdn.com", "evil.test", "storage.bunnycdn.com.evil.test", "127.0.0.1"):
        with pytest.raises(ValueError):
            BunnyStorage(host, "zone", "secret")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("PRAMANA_REQUIRE_MONGODB", "1")
    with pytest.raises(ValueError, match="requires MONGODB_URI"):
        get_settings()


def test_transport_checksum_redirects_limits_and_safe_errors():
    store = BunnyStorage("sg.storage.bunnycdn.com", "zone", "private-password")
    store.opener = MagicMock()
    key = "pramana/" + "a" * 64 + ".bin"
    store.request("PUT", key, b"encrypted")
    request = store.opener.open.call_args.args[0]
    assert request.full_url == "https://sg.storage.bunnycdn.com/zone/" + key
    assert request.get_header("Accesskey") == "private-password"
    assert len(request.get_header("Checksum")) == 64
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test") is None
    with pytest.raises(ValueError):
        store.request("DELETE", "../")
    with pytest.raises(AuditProblem):
        store.request("PUT", key, b"x" * (MAX_OBJECT_BYTES + 1))
    store.opener.open.side_effect = urllib.error.URLError("private-password")
    with pytest.raises(AuditProblem) as error:
        store.request("GET", key)
    assert "private-password" not in str(error.value)
    store.opener.open.side_effect = urllib.error.HTTPError("url", 404, "missing", {}, None)
    assert store.request("DELETE", key) == b""


@pytest.fixture
def retained():
    repository, storage = MagicMock(), MagicMock()
    repository.cipher = SnapshotCipher(json.dumps({"key": base64.b64encode(b"k" * 32).decode()}), "key")
    repository.get.return_value = {"expires_at": datetime.now(UTC) + timedelta(days=1)}
    files = RetainedFiles(repository, storage)
    files.records.find_one.return_value = None
    identity = AuditPrincipal("actor", "org", "reviewer")
    return files, identity


def test_original_encrypted_bound_to_org_integrity_and_expiry(retained):
    files, identity = retained
    files.save(identity, "run", b"original draft")
    record = files.records.insert_one.call_args.args[0]
    payload = files.storage.request.call_args.args[2]
    assert b"original draft" not in payload
    assert record["state"] == "pending"
    files.records.find_one.return_value = {**record, "state": "ready"}
    files.storage.request.return_value = payload
    assert files.original(identity, "run") == b"original draft"
    assert files.records.find_one.call_args.args[0]["organization_id"] == "org"
    files.storage.request.return_value = payload[:-1] + bytes([payload[-1] ^ 1])
    with pytest.raises(AuditProblem, match="decrypted"):
        files.original(identity, "run")
    files.repository.get.side_effect = AuditProblem(404, "expired")
    files.storage.reset_mock()
    with pytest.raises(AuditProblem):
        files.original(identity, "run")
    files.storage.request.assert_not_called()


def test_failed_upload_and_failed_delete_keep_retryable_references(retained):
    files, identity = retained
    files.storage.request.side_effect = AuditProblem(503, "offline")
    with pytest.raises(AuditProblem):
        files.save(identity, "run", b"original")
    files.records.insert_one.assert_called_once()
    files.records.update_one.assert_not_called()
    record = files.records.insert_one.call_args.args[0]
    files.records.find.return_value.limit.return_value = [record]
    with pytest.raises(AuditProblem):
        files.sweep()
    files.records.delete_one.assert_not_called()
    files.storage.request.side_effect = None
    files.sweep()
    files.records.delete_one.assert_called_once_with({"_id": record["_id"]})


def test_duplicate_upload_does_not_rewrite_ready_original(retained):
    files, identity = retained
    files.save(identity, "run", b"original")
    record = files.records.insert_one.call_args.args[0]
    files.records.find_one.return_value = {**record, "state": "ready"}
    files.storage.reset_mock()
    files.save(identity, "run", b"original")
    files.storage.request.assert_not_called()
    with pytest.raises(AuditProblem) as error:
        files.save(identity, "run", b"changed")
    assert error.value.status == 409
