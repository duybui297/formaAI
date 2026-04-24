"""
GET /health — liveness + basic readiness probe.

D-18: Docker healthcheck calls this endpoint.
Returns {"status": "ok"} for liveness.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe. Returns 200 {"status": "ok"} when the process is alive."""
    # TODO(phase-2): add JWT auth
    return {"status": "ok"}
