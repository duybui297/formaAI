"""
CORS middleware configuration.

INFRA-04: Allow Next.js dev origin (localhost:3000) only.
Never use allow_origins=["*"] — see Python security rules.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def add_cors_middleware(app: FastAPI) -> None:
    """Add CORS middleware allowing Next.js dev origin (INFRA-04).

    - allow_origins: localhost:3000 only (not "*")
    - allow_credentials: False (no cookies in Phase 1; re-evaluate for Phase 2 JWT)
    - allow_methods: restricted to what the API actually uses
    - allow_headers: Content-Type + Accept for JSON/multipart
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
