"""Create a private Render import file; never display credentials or overwrite a file."""

import os
from pathlib import Path


def main():
    from dotenv import dotenv_values
    values = {**dotenv_values(".env"), **dotenv_values(".env.audit"), **dotenv_values(".env.bunny")}
    names = ("MONGODB_URI", "MONGODB_DB", "PRAMANA_AUDIT_KEYS",
        "PRAMANA_AUDIT_ACTIVE_KEY", "PRAMANA_AUDIT_RETENTION_DAYS", "BUNNY_STORAGE_HOST",
        "BUNNY_STORAGE_ZONE", "BUNNY_STORAGE_PASSWORD")
    exported = {k: values[k] for k in names if values.get(k)}
    required = ("MONGODB_URI", "PRAMANA_AUDIT_KEYS", "PRAMANA_AUDIT_ACTIVE_KEY")
    if any(k not in exported for k in required):
        raise SystemExit("Required private MongoDB/audit configuration is missing.")
    exported.update(CORS_ORIGINS="https://pramana-frontend.onrender.com", PRAMANA_REQUIRE_MONGODB="1",
        PRAMANA_REQUIRE_AUDIT="1", PRAMANA_ENABLE_LOCAL_INTAKE="0")
    if all(exported.get(k) for k in names[-3:]):
        exported["PRAMANA_REQUIRE_BUNNY"] = "1"
    # dotenv quoting preserves JSON, hashes and spaces; these are not shell commands.
    content = "".join(k + "='" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'\n" for k, v in exported.items())
    output = Path(".env.render")
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
        handle.write(content)
    print("Created ignored .env.render for private import into the backend service only.")
    print("Bunny included." if "PRAMANA_REQUIRE_BUNNY" in exported else "Bunny is pending; no credentials were available.")


if __name__ == "__main__":
    main()
