"""
License validation middleware — TASK-2.3.

Enforces a valid, non-expired ACTIVE license on all /v1/** paths.
Excluded paths pass through without any license check:
  - /admin/**           (admin management routes)
  - /licenses/activate  (the activation endpoint itself)
  - /health             (liveness probe)
  - /docs, /openapi.json, /redoc  (FastAPI introspection)

Flow (mirrors the Spring Security OncePerRequestFilter diagram):
  1. Read X-License-Key header → hash_key() → cache_key = license:{hash}
  2. Redis GET → HIT:  deserialize; if status==ACTIVE and not expired → allow
  3. Redis MISS: query DB by key_hash; if ACTIVE and expired_at > now →
       repopulate Redis with remaining TTL → allow
  4. Any other case → 403 {"error": "LICENSE_INVALID", "code": "E4030"}

DB sessions are created directly from app.state.engine (not via Depends —
middleware runs outside the FastAPI DI graph).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.db.models import License, LicenseStatus
from app.licensing.keygen import hash_key

log = structlog.get_logger()


def _utcnow() -> datetime:
    """Return current UTC time.  Monkeypatch this in tests for clock injection."""
    return datetime.now(timezone.utc)


# Paths that bypass license enforcement entirely.
# Prefix-match: a path is excluded if it starts with any of these strings.
_EXCLUDED_PREFIXES = (
    "/admin/",            # admin management routes
    "/licenses/activate", # activation endpoint
    "/health",            # liveness probe
    "/docs",              # Swagger UI
    "/redoc",             # ReDoc UI
    "/openapi.json",      # OpenAPI schema
)

# Only enforce on paths that start with this prefix.
_ENFORCED_PREFIX = "/v1/"

_403_BODY = {"error": "LICENSE_INVALID", "code": "E4030"}


def _is_enforced(path: str) -> bool:
    """Return True iff this path needs a valid license."""
    if not path.startswith(_ENFORCED_PREFIX):
        return False
    for excl in _EXCLUDED_PREFIXES:
        if path.startswith(excl):
            return False
    return True


class LicenseValidationMiddleware(BaseHTTPMiddleware):
    """Starlette BaseHTTPMiddleware that gates /v1/** on a valid license."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if not _is_enforced(path):
            return await call_next(request)

        # --- read license key from header ------------------------------------
        raw_key = request.headers.get("X-License-Key")
        if not raw_key:
            log.info("license_middleware_missing_key", path=path)
            return JSONResponse(status_code=403, content=_403_BODY)

        key_hash = hash_key(raw_key)
        cache_key = f"license:{key_hash}"

        redis = request.app.state.redis

        # --- Redis HIT path --------------------------------------------------
        cached_raw = await redis.get(cache_key)
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except (json.JSONDecodeError, TypeError):
                log.warning("license_middleware_bad_cache", cache_key=cache_key)
                return JSONResponse(status_code=403, content=_403_BODY)

            if not _cache_entry_valid(cached):
                log.info("license_middleware_cache_invalid", status=cached.get("status"))
                return JSONResponse(status_code=403, content=_403_BODY)

            return await call_next(request)

        # --- Redis MISS path — fall back to DB -------------------------------
        engine = request.app.state.engine
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            result = await session.execute(
                select(License).where(License.key_hash == key_hash)
            )
            lic = result.scalar_one_or_none()

        if lic is None:
            log.info("license_middleware_db_miss", key_hash=key_hash[:8])
            return JSONResponse(status_code=403, content=_403_BODY)

        if lic.status != LicenseStatus.ACTIVE:
            log.info("license_middleware_not_active", status=lic.status.value)
            return JSONResponse(status_code=403, content=_403_BODY)

        now = _utcnow()
        expired_at = lic.expired_at
        if expired_at is not None:
            # SQLite stores as tz-naive; normalise to UTC-aware
            if expired_at.tzinfo is None:
                expired_at = expired_at.replace(tzinfo=timezone.utc)
            if expired_at <= now:
                log.info("license_middleware_expired", key_hash=key_hash[:8])
                return JSONResponse(status_code=403, content=_403_BODY)

        # --- repopulate Redis cache ------------------------------------------
        activated_at = lic.activated_at
        if activated_at is not None and activated_at.tzinfo is None:
            activated_at = activated_at.replace(tzinfo=timezone.utc)

        cache_payload = json.dumps(
            {
                "id": lic.id,
                "tier": lic.tier.value,
                "status": lic.status.value,
                "activated_at": activated_at.isoformat() if activated_at else None,
                "expired_at": expired_at.isoformat() if expired_at else None,
            }
        )
        remaining_ttl = (
            max(1, int((expired_at - now).total_seconds()))
            if expired_at is not None
            else 86400  # fallback: 1 day
        )
        await redis.set(cache_key, cache_payload, ex=remaining_ttl)
        log.info(
            "license_middleware_cache_repopulated",
            key_hash=key_hash[:8],
            ttl=remaining_ttl,
        )

        return await call_next(request)


def _cache_entry_valid(cached: dict) -> bool:
    """Return True iff the cached entry represents an ACTIVE, non-expired license."""
    if cached.get("status") != LicenseStatus.ACTIVE.value:
        return False

    expired_at_raw = cached.get("expired_at")
    if expired_at_raw is not None:
        try:
            expired_at = datetime.fromisoformat(expired_at_raw)
            if expired_at.tzinfo is None:
                expired_at = expired_at.replace(tzinfo=timezone.utc)
            if expired_at <= _utcnow():
                return False
        except (ValueError, TypeError):
            return False

    return True
