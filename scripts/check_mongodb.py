"""User-run Atlas smoke test. Environment variables are supplied by the caller."""

from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.domain import DraftVersion, ReviewDecision, ReviewRun
from app.repositories.mongodb_repository import MongoReviewRepository


def main() -> int:
    repository = None
    run_id = "connection-check-" + str(uuid4())
    written = False
    try:
        settings = get_settings()
        if not settings.mongodb_uri:
            print("FAIL: MONGODB_URI is missing. Run with: uv run --env-file .env python scripts/check_mongodb.py")
            return 1
        repository = MongoReviewRepository(settings.mongodb_uri, settings.mongodb_db)
        repository.start()
        print("PASS: connected to MongoDB and initialized the history index.")
        repository.record_review_run(ReviewRun(
            run_id, "lumadesk", DraftVersion("test-draft", "v1", "Fictional connection check."),
            datetime.now(UTC),
        ), 0)
        written = True
        event = repository.record_review_decision(run_id, ReviewDecision.REVISION, datetime.now(UTC))
        repository.close()
        repository = MongoReviewRepository(settings.mongodb_uri, settings.mongodb_db)
        repository.start()
        record = repository.get_review_record(run_id)
        if record is None or record.current_decision is None or record.current_decision.decision_id != event.decision_id:
            print("FAIL: review metadata or decision did not survive reconnecting.")
            return 1
        document = repository._runs.find_one({"_id": run_id})
        if not document or any(key in document for key in ("draft_text", "draft", "findings", "receipts")):
            print("FAIL: stored review metadata has an unexpected shape.")
            return 1
        print("PASS: review metadata and human decision survived a new database connection.")
        print("PASS: stored history contains no draft or receipt text.")
        return 0
    except Exception as error:
        # Driver messages can contain network or credential details. Never print them.
        print("FAIL: database check stopped (" + type(error).__name__ + ").")
        print("Check the URI/password, database-user permissions, and Atlas IP access list. Do not share secrets.")
        return 1
    finally:
        if repository is not None:
            if written:
                try:
                    result = repository._runs.delete_one({"_id": run_id})
                    if result.deleted_count:
                        print("Removed this check's temporary review record.")
                except Exception:
                    print("Could not remove the temporary test record: " + run_id)
            repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
