"""Environment-backed, non-secret application settings."""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]
    database_url: str | None


def get_settings() -> Settings:
    raw_origins = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
    cors_origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
    if not cors_origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one explicit origin.")

    database_url = os.getenv("DATABASE_URL")
    return Settings(cors_origins=cors_origins, database_url=database_url or None)

