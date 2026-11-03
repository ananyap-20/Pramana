"""Verify a private Bunny zone using one encrypted fictional test object."""

import os
from pathlib import Path
import secrets
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.bunny_storage import BunnyStorage


def main():
    storage, attempted = None, False
    key = "pramana/" + secrets.token_hex(32) + ".bin"
    try:
        storage = BunnyStorage.from_environment()
        if storage is None:
            print("FAIL: Bunny Storage settings are missing.")
            return 1
        storage.check_ready()
        cipher, nonce = AESGCM(AESGCM.generate_key(bit_length=256)), os.urandom(12)
        payload = cipher.encrypt(nonce, b"Fictional Pramana storage check.", b"check-v1")
        attempted = True
        storage.request("PUT", key, payload)
        restored = storage.request("GET", key)
        if cipher.decrypt(nonce, restored, b"check-v1") != b"Fictional Pramana storage check.":
            raise RuntimeError()
        print("PASS: encrypted object uploaded, downloaded and verified against Bunny.")
        return 0
    except Exception as error:
        print("FAIL: Bunny check stopped (" + type(error).__name__ + "). No credentials printed.")
        return 1
    finally:
        if storage and attempted:
            try:
                storage.request("DELETE", key)
                print("Removed this check's object.")
            except Exception:
                print("Cleanup failed; remove only this test object: " + key)


if __name__ == "__main__":
    raise SystemExit(main())
