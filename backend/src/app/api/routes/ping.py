"""
GET /api/v1/ping — trivial protected endpoint for load-testing the license validation
middleware hot path.

This endpoint does no DB work and no business logic — its only purpose is to be
a valid 200 target behind LicenseValidationMiddleware so the Redis O(1) GET
license:{hash} cache-hit path can be measured in isolation.

TASK-4.2-d: SLA target is P99 < 50ms for 1000 concurrent users with a pre-activated,
Redis-cached license key.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["internal"])


@router.get("/ping", summary="License middleware smoke check (load test target)")
async def ping() -> dict[str, bool]:
    """Returns 200 {"ok": true} iff the request passed LicenseValidationMiddleware.

    No DB access.  No business logic.  Exists solely as a hot-path SLA target.
    """
    return {"ok": True}
