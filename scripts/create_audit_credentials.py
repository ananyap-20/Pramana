"""Create a new private audit configuration without displaying secrets or overwriting files."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--role", choices=("reader", "reviewer", "admin"), default="reviewer")
    parser.add_argument("--output", type=Path, default=Path(".env.audit"))
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) for value in (args.actor, args.organization)):
        parser.error("Actor and organization must use 1-64 letters, digits, underscores or hyphens.")
    output = args.output.resolve()
    access_file = output.with_name(output.name + ".access-key")
    if output.exists() or access_file.exists():
        parser.error("Output already exists. Preserve existing identities and encryption keys.")
    token = secrets.token_urlsafe(32)
    identities = [{"token_sha256": hashlib.sha256(token.encode()).hexdigest(), "actor_id": args.actor,
                   "organization_id": args.organization, "role": args.role}]
    keys = {"key1": base64.b64encode(secrets.token_bytes(32)).decode()}
    content = ("PRAMANA_AUDIT_IDENTITIES='" + json.dumps(identities, separators=(",", ":")) + "'\n"
               "PRAMANA_AUDIT_KEYS='" + json.dumps(keys, separators=(",", ":")) + "'\n"
               "PRAMANA_AUDIT_ACTIVE_KEY=key1\nPRAMANA_AUDIT_RETENTION_DAYS=30\n")
    # Exclusive create and owner-only mode on platforms supporting it; never overwrite keys.
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
        handle.write(content)
    with os.fdopen(os.open(access_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    print("Created private server configuration and a separate access-key file. No secrets were printed.")
    print("Keep both files outside Git. Protect the encryption key in your secrets manager before using retained reviews.")


if __name__ == "__main__":
    main()
