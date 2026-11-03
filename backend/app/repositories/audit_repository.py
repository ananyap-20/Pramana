"""One atomic MongoDB document per review: immutable evidence plus bounded events."""

from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from app.audit_models import AuditEvent, AuditProblem, AuditRun, AuditSnapshot
from app.services.audit_security import AuditPrincipal, SnapshotCipher


class AuditRepository:
    def __init__(self, uri: str, database: str, cipher: SnapshotCipher, retention_days: int = 30):
        if not 1 <= retention_days <= 90:
            raise ValueError("Audit retention must be between 1 and 90 days.")
        self.client = MongoClient(uri, connect=False, tz_aware=True, timeoutMS=5000,
            serverSelectionTimeoutMS=5000, maxPoolSize=10, waitQueueTimeoutMS=5000)
        self.collection = self.client[database].get_collection("audit_reviews_v1",
            write_concern=WriteConcern(w="majority", j=True), read_concern=ReadConcern("majority"))
        self.cipher, self.retention_days = cipher, retention_days

    def start(self):
        self.client.admin.command("ping")
        self.collection.create_index([("organization_id", ASCENDING), ("request_id", ASCENDING)], unique=True)
        self.collection.create_index([("organization_id", ASCENDING), ("brand_id", ASCENDING), ("evaluated_at", DESCENDING), ("_id", DESCENDING)])
        self.collection.create_index("expires_at", expireAfterSeconds=0)

    def close(self):
        self.client.close()

    @staticmethod
    def scope(principal: AuditPrincipal, now: datetime | None = None):
        return {"organization_id": principal.organization_id, "expires_at": {"$gt": now or datetime.now(UTC)}}

    def existing(self, principal, request_id: str, request_digest: str):
        record = self.collection.find_one({**self.scope(principal), "request_id": request_id})
        if record and record["request_digest"] != request_digest:
            raise AuditProblem(409, "This request key was already used for a different review.")
        return record

    def save(self, principal, request_id, request_digest, snapshot: AuditSnapshot, metrics: list[dict], configuration_digest: str):
        analysis = snapshot.analysis
        now = datetime.now(UTC)
        document = {"_id": analysis.review_run_id, "schema_version": 1,
            "organization_id": principal.organization_id, "actor_id": principal.actor_id,
            "request_id": request_id, "request_digest": request_digest,
            "brand_id": analysis.brand_id, "draft_id": analysis.draft_id, "draft_version": analysis.draft_version,
            "draft_sha256": hashlib.sha256(analysis.draft_text.encode()).hexdigest(),
            "configuration_sha256": configuration_digest, "engine_version": "deterministic-v1",
            "evaluated_at": analysis.evaluated_at, "expires_at": now + timedelta(days=self.retention_days),
            "input_type": analysis.input_type, "finding_count": len(analysis.findings),
            "metrics": metrics, "revision": 0, "events": [],
            "snapshot": self.cipher.encrypt(principal.organization_id, analysis.review_run_id, snapshot.model_dump_json().encode())}
        try:
            self.collection.insert_one(document)
            return document
        except DuplicateKeyError:
            original = self.existing(principal, request_id, request_digest)
            if original:
                return original
            raise AuditProblem(409, "This request key is unavailable. Use a new key.") from None

    def get(self, principal, run_id, *, with_snapshot=False):
        document = self.collection.find_one({**self.scope(principal), "_id": run_id}, None if with_snapshot else {"snapshot": 0, "metrics": 0})
        if document is None:
            raise AuditProblem(404, "Review was not found or its retention period ended.")
        return document

    def snapshot(self, principal, document):
        try:
            snapshot = AuditSnapshot.model_validate_json(self.cipher.decrypt(principal.organization_id, document["_id"], document["snapshot"]))
        except (ValueError, TypeError, KeyError):
            raise AuditProblem(503, "Retained evidence could not be read. Contact the operator.") from None
        configuration_hash = hashlib.sha256(json.dumps(snapshot.configuration, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if (snapshot.analysis.review_run_id != document["_id"] or
                snapshot.analysis.brand_id != document["brand_id"] or
                snapshot.analysis.draft_id != document["draft_id"] or
                snapshot.analysis.draft_version != document["draft_version"] or
                hashlib.sha256(snapshot.analysis.draft_text.encode()).hexdigest() != document["draft_sha256"] or
                configuration_hash != document["configuration_sha256"]):
            raise AuditProblem(503, "Retained evidence failed its integrity check.")
        return snapshot

    def decision(self, principal, run_id, request_id, request_digest, decision, expected_revision):
        now = datetime.now(UTC)
        now = now.replace(microsecond=(now.microsecond // 1000) * 1000)  # BSON precision; retries return identical JSON.
        event = AuditEvent(decision_id=str(uuid4()), decision=decision, actor_id=principal.actor_id,
            revision=expected_revision + 1, request_id=request_id, decided_at=now)
        record = self.get(principal, run_id)
        previous = self._repeated_event(record, request_id, request_digest)
        if previous:
            return previous
        if expected_revision >= 100:
            raise AuditProblem(409, "The 100-decision history limit was reached.")
        result = self.collection.update_one({**self.scope(principal), "_id": run_id, "revision": expected_revision,
                                             "events.request_id": {"$ne": request_id}},
            {"$push": {"events": {**event.model_dump(), "request_digest": request_digest}}, "$inc": {"revision": 1}})
        if result.matched_count:
            return event
        # A concurrent identical retry returns the original event; a competing edit conflicts.
        previous = self._repeated_event(self.get(principal, run_id), request_id, request_digest)
        if previous:
            return previous
        raise AuditProblem(409, "Another reviewer changed this review. Reload it before deciding.")

    @staticmethod
    def _repeated_event(record, request_id, request_digest):
        for event in record["events"]:
            if event["request_id"] == request_id:
                if event["request_digest"] != request_digest:
                    raise AuditProblem(409, "This request key was already used for a different decision.")
                return AuditEvent.model_validate({k: v for k, v in event.items() if k != "request_digest"})
        return None

    def history(self, principal, brand_id, limit, cursor=None):
        query = {**self.scope(principal), "brand_id": brand_id}
        if cursor:
            # A run UUID is a stable keyset anchor; it must itself be visible in this organization.
            anchor = self.get(principal, cursor)
            if anchor["brand_id"] != brand_id:
                raise AuditProblem(404, "History cursor was not found.")
            query["$or"] = [{"evaluated_at": {"$lt": anchor["evaluated_at"]}},
                            {"evaluated_at": anchor["evaluated_at"], "_id": {"$lt": anchor["_id"]}}]
        documents = list(self.collection.find(query, {"snapshot": 0, "metrics": 0}).sort(
            [("evaluated_at", DESCENDING), ("_id", DESCENDING)]).limit(limit + 1))
        return documents[:limit], documents[limit - 1]["_id"] if len(documents) > limit else None

    def delete(self, principal, run_id):
        # Idempotent and organization-scoped, including records waiting for TTL cleanup.
        self.collection.delete_one({"organization_id": principal.organization_id, "_id": run_id})

    @staticmethod
    def summary(document):
        events = tuple(AuditEvent.model_validate({k: v for k, v in e.items() if k != "request_digest"}) for e in document["events"])
        fields = {k: document[k] for k in ("brand_id", "draft_id", "draft_version", "draft_sha256", "configuration_sha256",
            "engine_version", "evaluated_at", "expires_at", "actor_id", "request_id", "input_type", "finding_count", "revision")}
        return AuditRun(review_run_id=document["_id"], **fields, decision_history=events,
            current_decision=events[-1].decision if events else None,
            current_decision_at=events[-1].decided_at if events else None)

    def aggregate(self, principal, brand_id, start, end, now):
        # One aggregation command; every facet uses the same organization/period/retention cohort.
        return next(self.collection.aggregate([
            {"$match": {**self.scope(principal, now), "brand_id": brand_id, "evaluated_at": {"$gte": start, "$lt": end}}},
            {"$project": {"evaluated_at": 1, "finding_count": 1, "metrics": 1, "events.decision": 1}},
            {"$set": {"latest": {"$arrayElemAt": ["$events", -1]}}},
            {"$facet": {
                "totals": [{"$group": {"_id": None, "runs": {"$sum": 1}, "findings": {"$sum": "$finding_count"}, "events": {"$sum": {"$size": "$events"}}}}],
                "outcomes": [{"$group": {"_id": {"$ifNull": ["$latest.decision", "pending"]}, "count": {"$sum": 1}}}],
                "categories": [{"$unwind": "$metrics"}, {"$group": {"_id": "$metrics.category", "count": {"$sum": 1}}}],
                "rules": [{"$unwind": "$metrics"}, {"$group": {"_id": {"rule_id": "$metrics.rule_id", "version": "$metrics.rule_version"}, "count": {"$sum": 1}}},
                          {"$sort": {"count": -1, "_id.rule_id": 1, "_id.version": 1}}, {"$limit": 100}],
                "daily": [{"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$evaluated_at", "timezone": "UTC"}}, "runs": {"$sum": 1}, "findings": {"$sum": "$finding_count"}}}, {"$sort": {"_id": 1}}],
            }}], maxTimeMS=5000), {"totals": [], "outcomes": [], "categories": [], "rules": [], "daily": []})
