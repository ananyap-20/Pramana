"""Operator-issued credentials and authenticated encryption; no password database."""

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from pydantic import Field

from app.intake_models import ImmutableModel
from app.audit_models import AuditProblem


class AuditIdentity(ImmutableModel):
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)
    actor_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    organization_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    role: str = Field(pattern=r"^(reader|reviewer|admin)$")


@dataclass(frozen=True)
class AuditPrincipal:
    actor_id: str
    organization_id: str
    role: str


class AuditAuth:
    def __init__(self, raw: str):
        try:
            values = json.loads(raw)
            if not isinstance(values, list) or not 1 <= len(values) <= 100:
                raise ValueError()
            self.identities = tuple(AuditIdentity.model_validate(item) for item in values)
            if len({i.token_sha256 for i in self.identities}) != len(self.identities):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("Invalid audit identities configuration.") from None

    def authenticate(self, authorization: str | None) -> AuditPrincipal:
        token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
            raise HTTPException(401, "A valid audit access key is required.", headers={"WWW-Authenticate": "Bearer"})
        digest = hashlib.sha256(token.encode()).hexdigest()
        identity = next((i for i in self.identities if hmac.compare_digest(i.token_sha256, digest)), None)
        if identity is None:
            raise HTTPException(401, "A valid audit access key is required.", headers={"WWW-Authenticate": "Bearer"})
        return AuditPrincipal(identity.actor_id, identity.organization_id, identity.role)


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
