"""
License validation middleware — auto-select best license per authenticated user.

Enforces a valid, non-expired ACTIVE license on all /api/v1/** paths.
Excluded paths pass through without any license check:
  - /api/v1/admin/**      (admin management routes — superuser only anyway)
  - /api/v1/licenses/activate  (the activation endpoint itself)
  - /api/v1/health       (liveness probe)
  - /docs, /openapi.json, /redoc  (FastAPI introspection)
  - /api/v1/auth/*        (signup, login, verify-email, refresh, forgot/reset password, logout)

Auth flow per request:
  1. Decode JWT from Authorization: Bearer <token> header.
     Extract user_id and is_superuser from payload (no DB lookup needed).
  2. Superuser (is_superuser=True) → skip license check entirely.
  3. Unauthenticated / invalid JWT → 401 (NOT_AUTHENTICATED).
     This lets get_current_active_user return its own 401 rather than a confusing 403.
  4. Regular user → query all ACTIVE licenses for customer_id=user_id,
     pick the highest-tier one (ENTERPRISE > PRO > TRIAL), check expiry.
  5. No active license found → 403 (LICENSE_INVALID).
  6. Cache the best license in Redis under license:user:{user_id}:best.

Legacy support: X-License-Key header is still respected as a fallback
(so API keys / scripts that pass the header directly keep working).
It is superseded by the JWT-based flow for browser clients.

DB sessions are created directly from app.state.engine (not via Depends —
middleware runs outside the FastAPI DI graph).

Starlette 0.46+ uses BaseHTTPMiddleware with request-level dispatch
(signature: dispatch(self, request, call_next)) instead of the old ASGI
scope/receive/send signature.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.security import decode_access_token
from app.db.models import License, LicenseStatus
from app.licensing.keygen import hash_key
from app.licensing.plans import TIER_RANK

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

log = structlog.get_logger()


def _utcnow() -> datetime:
    """Return current UTC time.  Monkeypatch this in tests for clock injection."""
    return datetime.now(timezone.utc)


# Paths that bypass license enforcement entirely.
# Prefix-match: a path is excluded if it starts with any of these strings.
_EXCLUDED_PREFIXES = (
    "/api/v1/admin/",
    "/api/v1/licenses/activate",
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/logout",
)

_ENFORCED_PREFIX = "/api/v1/"

_401_BODY = {"error": "NOT_AUTHENTICATED", "code": "E4010"}
_403_BODY = {"error": "LICENSE_INVALID", "code": "E4030"}


def _is_enforced(path: str) -> bool:
    """Return True iff this path needs a valid license."""
    if not path.startswith(_ENFORCED_PREFIX):
        return False
    for excl in _EXCLUDED_PREFIXES:
        if path.startswith(excl):
            return False
    return True


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalise a datetime to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_license_active(lic: License) -> bool:
    """Return True if the license is ACTIVE and not expired."""
    if lic.status != LicenseStatus.ACTIVE:
        return False
    expired_at = _ensure_utc(lic.expired_at)
    if expired_at is not None and expired_at <= _utcnow():
        return False
    return True


def _pick_best_license(licenses: list[License]) -> License | None:
    """Return the highest-tier ACTIVE, non-expired license, or None."""
    best: License | None = None
    best_rank = -1
    for lic in licenses:
        if not _is_license_active(lic):
            continue
        rank = TIER_RANK.get(lic.tier, -1)
        if rank > best_rank:
            best = lic
            best_rank = rank
    return best


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


class LicenseValidationMiddleware(BaseHTTPMiddleware):
    """Starlette BaseHTTPMiddleware (Starlette 0.46+) gating /api/v1/** on a valid license."""

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        path = request.url.path
        root_path = request.scope.get("root_path", "")

        # Handle root_path prefix so middleware works behind a reverse proxy
        if root_path and path.startswith(root_path):
            path = path[len(root_path):]

        if not _is_enforced(path):
            return await call_next(request)

        redis = request.app.state.redis
        engine = request.app.state.engine

        # --- Step 1: JWT-based auth (primary path for browser clients) ----------
        auth_header = request.headers.get("authorization", "")
        user_id: str | None = None
        is_superuser: bool = False

        if auth_header.startswith("Bearer "):
            payload = decode_access_token(auth_header[7:])
            if payload:
                user_id = payload.get("sub")
                is_superuser = bool(payload.get("superuser", False))

        # --- Step 2: Superuser → skip license check entirely --------------------
        if is_superuser:
            return await call_next(request)

        # --- Step 3: No JWT → 401 (let auth dependency return its own 401) ------
        if not user_id:
            raw_key = request.headers.get("x-license-key")
            if not raw_key:
                log.info("license_middleware_missing_auth", path=path)
                return JSONResponse(status_code=401, content=_401_BODY)

            return await self._handle_legacy_key(
                raw_key=raw_key,
                redis=redis,
                engine=engine,
                request=request,
                call_next=call_next,
            )

        # --- Step 4: Regular user → auto-select best active license -------------
        return await self._handle_jwt_user(
            user_id=user_id,
            redis=redis,
            engine=engine,
            request=request,
            call_next=call_next,
        )

    async def _handle_legacy_key(
        self,
        raw_key: str,
        redis,
        engine,
        request: Request,
        call_next,
    ) -> Response:
        """Handle X-License-Key header — legacy path for scripts/API keys."""
        key_hash = hash_key(raw_key)
        cache_key = f"license:{key_hash}"

        # Redis HIT
        cached_raw = await redis.get(cache_key)
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except (json.JSONDecodeError, TypeError):
                log.warning("license_middleware_bad_cache", cache_key=cache_key)
                return JSONResponse(status_code=403, content=_403_BODY)

            if not _cache_entry_valid(cached):
                log.info(
                    "license_middleware_cache_invalid",
                    status=cached.get("status"),
                )
                return JSONResponse(status_code=403, content=_403_BODY)

            return await call_next(request)

        # Redis MISS → DB lookup
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                select(License).where(License.key_hash == key_hash)
            )
            lic = result.scalar_one_or_none()

        if lic is None:
            log.info("license_middleware_db_miss", key_hash=key_hash[:8])
            return JSONResponse(status_code=403, content=_403_BODY)

        if not _is_license_active(lic):
            log.info("license_middleware_inactive_or_expired", key_hash=key_hash[:8])
            return JSONResponse(status_code=403, content=_403_BODY)

        # Repopulate Redis cache
        now = _utcnow()
        expired_at = _ensure_utc(lic.expired_at)
        activated_at = _ensure_utc(lic.activated_at)
        cache_payload = json.dumps(
            {
                "id": lic.id,
                "tier": lic.tier.value,
                "status": lic.status.value,
                "activated_at": activated_at.isoformat() if activated_at else None,
                "expired_at": expired_at.isoformat() if expired_at else None,
            }
        )
        ttl = (
            max(1, int((expired_at - now).total_seconds()))
            if expired_at is not None
            else 86400
        )
        await redis.set(cache_key, cache_payload, ex=ttl)
        log.info("license_middleware_cache_repopulated", key_hash=key_hash[:8], ttl=ttl)

        return await call_next(request)

    async def _handle_jwt_user(
        self,
        user_id: str,
        redis,
        engine,
        request: Request,
        call_next,
    ) -> Response:
        """Handle JWT-authenticated user: auto-select best active license."""
        cache_key = f"license:user:{user_id}:best"

        # Redis HIT
        cached_raw = await redis.get(cache_key)
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
            except (json.JSONDecodeError, TypeError):
                log.warning(
                    "license_middleware_user_cache_bad",
                    user_id=user_id[:8],
                )
                await redis.delete(cache_key)
            else:
                if _cache_entry_valid(cached):
                    return await call_next(request)
                # Expired / inactive — invalidate and fall through to DB
                await redis.delete(cache_key)

        # Redis MISS or stale → query DB for all ACTIVE licenses for this user
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                select(License).where(
                    License.customer_id == user_id,
                    License.status == LicenseStatus.ACTIVE,
                )
            )
            licenses = list(result.scalars().all())

        best = _pick_best_license(licenses)
        if best is None:
            log.info(
                "license_middleware_no_active_license",
                user_id=user_id[:8],
                total_licenses=len(licenses),
            )
            return JSONResponse(status_code=403, content=_403_BODY)

        # Repopulate Redis cache
        now = _utcnow()
        expired_at = _ensure_utc(best.expired_at)
        activated_at = _ensure_utc(best.activated_at)
        cache_payload = {
            "id": best.id,
            "tier": best.tier.value,
            "status": best.status.value,
            "activated_at": activated_at.isoformat() if activated_at else None,
            "expired_at": expired_at.isoformat() if expired_at else None,
        }
        ttl = (
            max(1, int((expired_at - now).total_seconds()))
            if expired_at is not None
            else 86400
        )
        await redis.set(cache_key, json.dumps(cache_payload), ex=ttl)
        log.info(
            "license_middleware_cache_repopulated",
            user_id=user_id[:8],
            license_id=best.id,
            tier=best.tier.value,
        )

        return await call_next(request)
