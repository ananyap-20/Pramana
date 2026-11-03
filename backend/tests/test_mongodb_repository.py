"""Offline contract checks; the user-run smoke script tests a real MongoDB server."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pymongo.errors import AutoReconnect
import pytest

from app.config import get_settings
from app.domain import DraftVersion, ReviewDecision, ReviewRun
from app.main import create_app
from app.repositories.demo_repository import UnknownReviewRunError
from app.repositories.mongodb_repository import DecisionLimitError, MongoReviewRepository


@pytest.fixture
def mongo(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("app.repositories.mongodb_repository.MongoClient", lambda *a, **kw: client)
    repository = MongoReviewRepository("mongodb://localhost", "pramana")
    return repository, client, client.__getitem__.return_value.get_collection.return_value


def test_storage_keeps_metadata_and_never_sends_draft_text(mongo):
    repository, _, collection = mongo
    run = ReviewRun("run-1", "lumadesk", DraftVersion("draft-1", "v1", "PRIVATE DRAFT"), datetime.now(UTC))
    repository.record_review_run(run, 4)
    document = collection.insert_one.call_args.args[0]
    assert document["_id"] == "run-1"
    assert document["finding_count"] == 4
    assert set(document) == {"_id", "brand_id", "draft_id", "draft_version", "evaluated_at", "finding_count", "decisions"}
    assert "PRIVATE DRAFT" not in str(document)


def test_decision_append_is_atomic_and_bounded(mongo):
    repository, _, collection = mongo
    collection.update_one.return_value.matched_count = 1
    event = repository.record_review_decision("run-1", ReviewDecision.APPROVED, datetime.now(UTC))
    query, update = collection.update_one.call_args.args
    assert query == {"_id": "run-1", "decisions.99": {"$exists": False}}
    assert update["$push"]["decisions"]["decision_id"] == event.decision_id
    assert update["$push"]["decisions"]["decision"] == "approved"
    collection.find_one.assert_not_called()


def test_unknown_run_and_full_history_have_distinct_errors(mongo):
    repository, _, collection = mongo
    collection.update_one.return_value.matched_count = 0
    collection.find_one.return_value = None
    with pytest.raises(UnknownReviewRunError):
        repository.record_review_decision("absent", ReviewDecision.REVISION, datetime.now(UTC))
    collection.find_one.return_value = {"_id": "full"}
    with pytest.raises(DecisionLimitError):
        repository.record_review_decision("full", ReviewDecision.REVISION, datetime.now(UTC))


def test_history_round_trip_and_query_bound(mongo):
    repository, _, collection = mongo
    now = datetime.now(UTC)
    document = {"_id": "run-1", "brand_id": "lumadesk", "draft_id": "d1", "draft_version": "v1",
                "evaluated_at": now, "finding_count": 4,
                "decisions": [{"decision_id": "e1", "decision": "revision", "decided_at": now}]}
    collection.find_one.return_value = document
    record = repository.get_review_record("run-1")
    assert record.current_decision.decision == ReviewDecision.REVISION
    collection.find.return_value.sort.return_value.limit.return_value = [document]
    assert repository.list_review_runs("lumadesk") == [record]
    collection.find.assert_called_once_with({"brand_id": "lumadesk"})
    collection.find.return_value.sort.return_value.limit.assert_called_once_with(100)


def test_configuration_hides_uri_and_rejects_invalid_settings(monkeypatch):
    secret = "mongodb://user:DO_NOT_DISPLAY@localhost"
    monkeypatch.setenv("MONGODB_URI", secret)
    monkeypatch.setenv("MONGODB_DB", "pramana")
    assert secret not in repr(get_settings())
    monkeypatch.setenv("MONGODB_DB", "admin")
    with pytest.raises(ValueError, match="application database"):
        get_settings()
    monkeypatch.setenv("MONGODB_DB", "pramana")
    monkeypatch.setenv("MONGODB_URI", "")
    with pytest.raises(ValueError, match="MongoDB connection string"):
        get_settings()


def test_api_reports_selected_storage_and_safe_database_errors(monkeypatch, mongo):
    repository, _, collection = mongo
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost")
    monkeypatch.setenv("MONGODB_DB", "pramana")
    monkeypatch.setattr("app.main.MongoReviewRepository", lambda *a: repository)
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["persistence"] == "mongodb_review_metadata"
        result = client.post("/api/reviews/analyze", json={"brand_id": "lumadesk", "draft_text": "dashboard"})
        assert result.status_code == 200
        assert result.json()["persistence"] == "mongodb_review_metadata"
        assert result.json()["draft_text"] == "dashboard"
        collection.insert_one.side_effect = AutoReconnect("secret database connection details")
        failed = client.post("/api/reviews/analyze", json={"brand_id": "lumadesk", "draft_text": "dashboard"})
        assert failed.status_code == 503
        assert "secret database" not in failed.text
        repository._client.admin.command.side_effect = AutoReconnect("secret connection URI")
        assert client.get("/health").status_code == 503


def test_configured_database_startup_failure_never_falls_back(monkeypatch, mongo):
    repository, client, _ = mongo
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost")
    monkeypatch.setenv("MONGODB_DB", "pramana")
    monkeypatch.setattr("app.main.MongoReviewRepository", lambda *a: repository)
    client.admin.command.side_effect = AutoReconnect("secret")
    with pytest.raises(RuntimeError, match="MongoDB is unavailable"):
        with TestClient(create_app()):
            pass
    client.close.assert_called_once()
