"""Create optional audit encryption settings without any user credentials."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.audit"))
    args = parser.parse_args()
    content = ("PRAMANA_AUDIT_KEYS='" + json.dumps({"key1": base64.b64encode(secrets.token_bytes(32)).decode()}) + "'\n"
               "PRAMANA_AUDIT_ACTIVE_KEY=key1\nPRAMANA_AUDIT_RETENTION_DAYS=30\n")
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
        handle.write(content)
    print("Created private audit encryption configuration. No secrets were printed.")


if __name__ == "__main__":
    main()
