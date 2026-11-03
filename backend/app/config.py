"""Environment-backed, non-secret application settings."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit

from app.intake_models import IntakeLimits


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]
    database_url: str | None
    intake_enabled: bool
    intake_limits: IntakeLimits
    tesseract_cmd: str
    tessdata_dir: str | None
    mongodb_uri: str | None = field(default=None, repr=False)
    mongodb_db: str = "pramana"


def get_settings() -> Settings:
    raw_origins = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
    cors_origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
    if not cors_origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one explicit origin.")
    for origin in cors_origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or
                parsed.path or parsed.query or parsed.fragment or "*" in origin or
                (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})):
            raise ValueError("CORS_ORIGINS must be exact HTTPS origins (HTTP is loopback-only).")

    database_url = os.getenv("DATABASE_URL")
    mongodb_uri = os.getenv("MONGODB_URI")
    if os.getenv("PRAMANA_REQUIRE_MONGODB") == "1" and not mongodb_uri:
        raise ValueError("Deployment requires MONGODB_URI; memory storage is disabled.")
    if mongodb_uri is not None:
        mongodb_uri = mongodb_uri.strip()
        if not mongodb_uri.startswith(("mongodb+srv://", "mongodb://")):
            raise ValueError("MONGODB_URI must be a MongoDB connection string.")
    mongodb_db = os.getenv("MONGODB_DB", "pramana").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", mongodb_db) or mongodb_db in {"admin", "local", "config"}:
        raise ValueError("MONGODB_DB must be an application database name using letters, digits, underscores or hyphens.")
    return Settings(
        cors_origins=cors_origins, database_url=database_url or None,
        intake_enabled=os.getenv("PRAMANA_ENABLE_LOCAL_INTAKE", "1") == "1",
        intake_limits=IntakeLimits.model_validate_json(os.getenv("PRAMANA_INTAKE_LIMITS", "{}")),
        tesseract_cmd=os.getenv("TESSERACT_CMD", "tesseract"),
        tessdata_dir=os.getenv("TESSDATA_DIR") or None,
        mongodb_uri=mongodb_uri,
        mongodb_db=mongodb_db,
    )

