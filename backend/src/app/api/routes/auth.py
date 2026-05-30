"""
Auth routes: register, login, logout, refresh, forgot-password, reset-password.

POST /auth/register        — create account
POST /auth/login           — email+password → 15-min access token + 30-d httpOnly refresh cookie
POST /auth/refresh         — rotate refresh cookie, issue new 15-min access token (CSRF required)
POST /auth/logout          — clear cookie, revoke refresh
GET  /auth/me              — return current user info (protected)
POST /auth/forgot-password — send reset email (or silent success for security)
POST /auth/reset-password  — validate token + update password
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import structlog
from aiosmtplib import SMTP
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_password_reset_token,
    hash_password,
    verify_password,
)
from app.db.models import PasswordResetToken, User
from app.db.session import get_session
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.api.deps import get_current_active_user, get_redis

log = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])

CSRF_COOKIE = "csrf_token"
REFRESH_COOKIE = "refresh_token"

# Helpers
async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


def _lockout_key(user_id: str, ip: str) -> str:
    return f"lockout:{user_id}:{ip}"


def _attempt_key(user_id: str, ip: str) -> str:
    return f"login_attempts:{user_id}:{ip}"


async def _check_lockout(
    redis: Redis, user_id: str, ip: str, settings
) -> None:
    key = _lockout_key(user_id, ip)
    locked = await redis.get(key)
    if locked:
        ttl = await redis.ttl(key)
        wait_sec = max(int(ttl), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many failed attempts. Please try again in {wait_sec // 60 + 1} minute(s)."
            ),
        )


async def _record_failed_attempt(
    redis: Redis, user_id: str, ip: str, settings
) -> None:
    key = _attempt_key(user_id, ip)
    lockout_key = _lockout_key(user_id, ip)

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.login_attempt_window_minutes * 60)
    results = await pipe.execute()
    count = results[0]  # current count after incr

    if count >= settings.login_max_attempts:
        await redis.setex(
            lockout_key,
            settings.login_lockout_minutes * 60,
            "1",
        )
        # Also expire the attempt counter so window resets after lockout
        await redis.delete(key)
        log.warning("user_locked_out", user_id=user_id, ip=ip)


async def _clear_failed_attempts(redis: Redis, user_id: str, ip: str) -> None:
    await redis.delete(_attempt_key(user_id, ip))
    await redis.delete(_lockout_key(user_id, ip))


def _csrf_token(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE, "")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _send_reset_email(
    to_email: str, token: str, base_url: str
) -> None:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_email", to=to_email)
        return

    reset_url = f"{base_url}/reset-password?token={token}"
    body = (
        f"Hello,\n\n"
        f"You requested a password reset for your Forma account.\n\n"
        f"Click the link below to set a new password (expires in 1 hour):\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n"
    )

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = "Reset your Forma password"
    msg.set_content(body)

    try:
        smtp = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=settings.smtp_tls,
        )
        await smtp.connect()
        await smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        await smtp.send_message(msg)
        await smtp.quit()
        log.info("reset_email_sent", to=to_email)
    except Exception as exc:
        log.error("smtp_send_failed", to=to_email, error=str(exc))


# Routes
@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    existing = await _get_user_by_email(session, body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        email_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    log.info("user_registered", user_id=user.id, email=user.email)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    settings = get_settings()
    ip = _client_ip(request)
    user = await _get_user_by_email(session, body.email)

    password_ok = user is not None and verify_password(body.password, user.hashed_password)

    if user is not None:
        await _check_lockout(redis, user.id, ip, settings)

    if not password_ok or user is None:
        detail = "Incorrect email or password"
        if user is not None:
            await _record_failed_attempt(redis, user.id, ip, settings)
            log.info("login_failed", user_id=user.id, ip=ip, reason="bad_password")
        else:
            log.info("login_failed", email=body.email.lower(), ip=ip, reason="unknown_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    await _clear_failed_attempts(redis, user.id, ip)

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    # Set rotating refresh token cookie
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        httponly=False,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )

    log.info("user_logged_in", user_id=user.id, email=user.email, ip=ip)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
) -> RefreshTokenResponse:
    settings = get_settings()

    raw_refresh = request.cookies.get(REFRESH_COOKIE, "")
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    payload = decode_refresh_token(raw_refresh)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    ip = _client_ip(request)
    await _check_lockout(redis, user_id, ip, settings)

    csrf_header = request.headers.get("x-csrf-token", "")
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    if not csrf_header or csrf_header != csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Verify user still exists and is active
    from app.db.session import get_session as _get_s
    async with _get_s() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated",
            )

    # Rotate: issue new access + refresh tokens
    new_access = create_access_token(data={"sub": user_id})
    new_refresh = create_refresh_token(data={"sub": user_id})
    new_csrf = secrets.token_urlsafe(32)

    # Set new cookies (path=/api so it doesn't conflict with static assets if any)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=new_csrf,
        httponly=False,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )

    log.info("token_refreshed", user_id=user_id, ip=ip)

    return RefreshTokenResponse(access_token=new_access)


@router.post("/logout", status_code=204, response_model=None)
async def logout(request: Request, response: Response) -> None:
    """Clear refresh and CSRF cookies. Client drops local access token separately."""
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    response.delete_cookie(key=CSRF_COOKIE, path="/")
    response.delete_cookie(key="forma_access_token", path="/")


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
    check_only: bool = Query(False),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    user = await _get_user_by_email(session, body.email)

    if check_only and user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )

    if user is None:
        return MessageResponse(
            message="If an account with that email exists, a reset link has been sent."
        )

    # Rate-limit: skip token creation and email send if a reset was already requested
    # within the cooldown window.
    settings = get_settings()
    rate_limit_key = f"forgot_password:{body.email.lower()}"
    if not check_only:
        cooldown_ttl = await redis.get(rate_limit_key)
        if cooldown_ttl is not None:
            return MessageResponse(
                message="If an account with that email exists, a reset link has been sent."
            )
        await redis.setex(rate_limit_key, settings.forgot_password_cooldown_seconds, "1")

    # Invalidate any existing unused reset tokens for this user
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for old_token in result.scalars().all():
        old_token.used_at = datetime.now(timezone.utc)

    raw_token = generate_password_reset_token(user.email)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    prt = PasswordResetToken(
        token=raw_token,
        user_id=user.id,
        expires_at=expires_at,
    )
    session.add(prt)
    await session.commit()

    if not check_only:
        await _send_reset_email(user.email, raw_token, "http://localhost:8080")

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent."
    )


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    result = await session.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token == body.token)
        .where(PasswordResetToken.used_at.is_(None))
    )
    prt = result.scalar_one_or_none()

    if prt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if prt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Look up user
    user_result = await session.execute(
        select(User).where(User.id == prt.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Update password
    user.hashed_password = hash_password(body.new_password)
    prt.used_at = datetime.now(timezone.utc)

    await session.commit()

    log.info("password_reset_complete", user_id=user.id, email=user.email)

    return MessageResponse(message="Password has been reset successfully. Please log in.")
