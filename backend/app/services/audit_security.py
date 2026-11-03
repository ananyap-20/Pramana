"""Audit partition metadata and authenticated snapshot encryption."""

import base64
from dataclasses import dataclass
import json
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.audit_models import AuditProblem


@dataclass(frozen=True)
class AuditPrincipal:
    actor_id: str
    organization_id: str
    role: str


class SnapshotCipher:
    def __init__(self, raw_keys: str, active_key: str):
        try:
            values = json.loads(raw_keys)
            if not isinstance(values, dict) or not 1 <= len(values) <= 8:
                raise ValueError()
            self.keys = {kid: base64.b64decode(value, validate=True) for kid, value in values.items()}
            if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", kid) or len(value) != 32 for kid, value in self.keys.items()):
                raise ValueError()
            if active_key not in self.keys:
                raise ValueError()
            self.active_key = active_key
        except (ValueError, TypeError):
            raise ValueError("Invalid audit encryption key configuration.") from None

    @staticmethod
    def aad(organization: str, run_id: str) -> bytes:
        return json.dumps(["pramana-audit-snapshot-v1", organization, run_id], separators=(",", ":")).encode()

    def encrypt(self, organization: str, run_id: str, payload: bytes) -> dict:
        if len(payload) > 2 * 1024 * 1024:
            raise AuditProblem(413, "Review snapshot exceeds its retention limit.")
        nonce = os.urandom(12)
        return {"key_id": self.active_key, "nonce": nonce,
                "ciphertext": AESGCM(self.keys[self.active_key]).encrypt(nonce, payload, self.aad(organization, run_id))}

    def decrypt(self, organization: str, run_id: str, envelope: dict) -> bytes:
        try:
            return AESGCM(self.keys[envelope["key_id"]]).decrypt(bytes(envelope["nonce"]), bytes(envelope["ciphertext"]), self.aad(organization, run_id))
        except (KeyError, ValueError, TypeError, InvalidTag):
            raise AuditProblem(503, "Retained evidence cannot be decrypted. Contact the operator.") from None
