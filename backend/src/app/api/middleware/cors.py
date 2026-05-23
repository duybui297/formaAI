"""
CORS middleware configuration.

INFRA-04: Allow Next.js dev origin by default; configurable for prod via
CORS_ALLOWED_ORIGINS env var (comma-separated list).
Never use allow_origins=["*"] — see Python security rules.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _parse_origins() -> list[str]:
    """Parse CORS_ALLOWED_ORIGINS env (comma-separated). Defaults to dev origin.

    Examples:
        CORS_ALLOWED_ORIGINS=http://localhost:3000
        CORS_ALLOWED_ORIGINS=https://translate.example.com,https://www.translate.example.com
    """
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def add_cors_middleware(app: FastAPI) -> None:
    """Add CORS middleware allowing configured origins (INFRA-04).

    PATCH-DOC methods (segments edit) added — review UI sends PATCH.
    DELETE added for glossary delete in Phase 2.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
