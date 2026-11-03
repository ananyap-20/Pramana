"""Durable demo history metadata; no drafts, receipts, or uploaded files are stored."""

from datetime import datetime
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern

from app.domain import BrandConfiguration, ReviewDecision, ReviewDecisionRecord, ReviewRecord, ReviewRun
from app.repositories.demo_repository import MAX_REVIEW_RECORDS, UnknownReviewRunError
from app.services.seed_data import build_lumadesk_configuration


MAX_DECISIONS_PER_RUN = 100


class StorageUnavailableError(RuntimeError):
    """Safe public error without driver details or credentials."""


class DecisionLimitError(ValueError):
    """A bounded demo review has exhausted its decision history."""


class MongoReviewRepository:
    persistence = "mongodb_review_metadata"

    def __init__(self, uri: str, database: str) -> None:
        self._brand = build_lumadesk_configuration()
        try:
            self._client = MongoClient(
                uri, connect=False, tz_aware=True, timeoutMS=5000,
                serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                maxPoolSize=10, waitQueueTimeoutMS=5000,
            )
            self._runs = self._client[database].get_collection(
                "review_runs", write_concern=WriteConcern(w="majority"),
            )
        except (PyMongoError, ValueError):
            raise StorageUnavailableError("MongoDB configuration could not be initialized.") from None

    def start(self) -> None:
        self.check_ready()
        self._runs.create_index([("brand_id", ASCENDING), ("evaluated_at", DESCENDING)])

    def check_ready(self) -> None:
        self._client.admin.command("ping")

    def close(self) -> None:
        self._client.close()

    def get_brand(self, brand_id: str) -> BrandConfiguration | None:
        return self._brand if brand_id == self._brand.brand_id else None

    def record_review_run(self, review_run: ReviewRun, finding_count: int) -> None:
        self._runs.insert_one({
            "_id": review_run.review_run_id,
            "brand_id": review_run.brand_id,
            "draft_id": review_run.draft.draft_id,
            "draft_version": review_run.draft.version,
            "evaluated_at": review_run.evaluated_at,
            "finding_count": finding_count,
            "decisions": [],
        })

    def get_review_record(self, review_run_id: str) -> ReviewRecord | None:
        document = self._runs.find_one({"_id": review_run_id})
        return self._record(document) if document is not None else None

    def record_review_decision(
        self, review_run_id: str, decision: ReviewDecision, decided_at: datetime,
    ) -> ReviewDecisionRecord:
        event = ReviewDecisionRecord(str(uuid4()), decision, decided_at)
        # One atomic append preserves concurrent decisions without read/replace races.
        result = self._runs.update_one(
            {"_id": review_run_id, f"decisions.{MAX_DECISIONS_PER_RUN - 1}": {"$exists": False}},
            {"$push": {"decisions": {
                "decision_id": event.decision_id,
                "decision": event.decision.value,
                "decided_at": event.decided_at,
            }}},
        )
        if not result.matched_count:
            if self._runs.find_one({"_id": review_run_id}, {"_id": 1}) is None:
                raise UnknownReviewRunError("Review run was not found in the stored history.")
            raise DecisionLimitError("This demo review has reached its 100-decision limit.")
        return event

    def list_review_runs(self, brand_id: str) -> list[ReviewRecord]:
        documents = self._runs.find({"brand_id": brand_id}).sort(
            [("evaluated_at", DESCENDING), ("_id", DESCENDING)],
        ).limit(MAX_REVIEW_RECORDS)
        return [self._record(document) for document in documents]

    @staticmethod
    def _record(document: dict) -> ReviewRecord:
        return ReviewRecord(
            review_run_id=document["_id"], brand_id=document["brand_id"],
            draft_id=document["draft_id"], draft_version=document["draft_version"],
            evaluated_at=document["evaluated_at"], finding_count=document["finding_count"],
            decisions=tuple(ReviewDecisionRecord(
                decision_id=event["decision_id"], decision=ReviewDecision(event["decision"]),
                decided_at=event["decided_at"],
            ) for event in document["decisions"]),
        )
