"""
GET /glossaries — Phase 2 stub.

UPLD-04 deferred to Phase 2 per D-15.
Endpoint exists so the frontend can render an empty picker without errors.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/glossaries")
async def list_glossaries() -> dict:
    """
    UPLD-04 stub: Glossary CRUD and picker UI are deferred to Phase 2 (D-15).
    Returns empty list so Phase 2 frontend can build the picker against a working endpoint.
    # TODO(phase-2): implement glossary CRUD + picker, add JWT auth
    """
    return {"glossaries": []}
