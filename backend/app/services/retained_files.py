"""Encrypted originals linked to retained reviews; Mongo tracks retryable cleanup."""

from datetime import UTC, datetime, timedelta
import hashlib
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.audit_models import AuditProblem


class RetainedFiles:
    def __init__(self, repository, storage):
        self.repository, self.storage = repository, storage
        self.records = repository.collection.database.get_collection("audit_files_v1",
            write_concern=repository.collection.write_concern)

    def start(self):
        # No Mongo TTL: references must survive until Bunny deletion succeeds.
        self.records.create_index([("expires_at", ASCENDING)])
        self.records.create_index([("organization_id", ASCENDING), ("run_id", ASCENDING)])
        self.storage.check_ready()

    def save(self, identity, run_id, content):
        if not content or len(content) > 5 * 1024 * 1024:
            raise AuditProblem(413, "Original must contain at most 5 MiB.")
        parent = self.repository.get(identity, run_id)
        record_id = hashlib.sha256((identity.organization_id + ":" + run_id).encode()).hexdigest()
        existing = self.records.find_one({"_id": record_id})
        if existing:
            if existing["sha256"] != hashlib.sha256(content).hexdigest():
                raise AuditProblem(409, "A different original is already attached to this review.")
            if existing["state"] == "ready":
                return
            if existing["expires_at"] <= datetime.now(UTC):
                self.sweep(identity.organization_id, run_id)
                return self.save(identity, run_id, content)
            raise AuditProblem(503, "Original retention is pending. Retry after cleanup or contact the operator.")
        key_id = self.repository.cipher.active_key
        nonce = os.urandom(12)
        object_key = "pramana/" + secrets.token_hex(32) + ".bin"
        aad = ("pramana-original-v1:" + record_id).encode()
        encrypted = AESGCM(self.repository.cipher.keys[key_id]).encrypt(nonce, content, aad)
        # Persist intent BEFORE the network write. Failed/ambiguous uploads remain sweepable.
        record = {"_id": record_id, "organization_id": identity.organization_id,
            "run_id": run_id, "object_key": object_key, "key_id": key_id, "nonce": nonce,
            "sha256": hashlib.sha256(content).hexdigest(), "state": "pending",
            "expires_at": datetime.now(UTC) + timedelta(minutes=5), "retain_until": parent["expires_at"]}
        try:
            self.records.insert_one(record)
        except DuplicateKeyError:
            raise AuditProblem(409, "Original retention is already in progress. Retry shortly.") from None
        self.storage.request("PUT", object_key, encrypted)
        self.records.update_one({"_id": record_id}, {"$set": {"state": "ready", "expires_at": parent["expires_at"]}})
        try:
            self.repository.get(identity, run_id)
        except AuditProblem:
            self.delete(identity, run_id)
            raise

    def original(self, identity, run_id):
        self.repository.get(identity, run_id)
        record = self.records.find_one({"organization_id": identity.organization_id, "run_id": run_id,
            "state": "ready", "expires_at": {"$gt": datetime.now(UTC)}})
        if not record:
            raise AuditProblem(404, "No retained original is available for this review.")
        content = self.storage.request("GET", record["object_key"])
        try:
            plain = AESGCM(self.repository.cipher.keys[record["key_id"]]).decrypt(
                bytes(record["nonce"]), content, ("pramana-original-v1:" + record["_id"]).encode())
        except (KeyError, ValueError, InvalidTag):
            raise AuditProblem(503, "Original could not be decrypted. Contact the operator.") from None
        if hashlib.sha256(plain).hexdigest() != record["sha256"]:
            raise AuditProblem(503, "Original integrity verification failed.")
        return plain

    def delete(self, identity, run_id):
        # Mark first so failures/crashes are retried, even after the parent disappears.
        self.records.update_many({"organization_id": identity.organization_id, "run_id": run_id},
            {"$set": {"expires_at": datetime.now(UTC)}})
        self.sweep(identity.organization_id, run_id)

    def sweep(self, organization=None, run_id=None):
        query = {"expires_at": {"$lte": datetime.now(UTC)}}
        if organization is not None:
            query.update(organization_id=organization, run_id=run_id)
        for record in self.records.find(query).limit(100):
            self.storage.request("DELETE", record["object_key"])
            self.records.delete_one({"_id": record["_id"]})
